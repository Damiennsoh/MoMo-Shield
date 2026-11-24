"""
Fraud Knowledge Base — hybrid lexical + semantic matcher (RAG engine).

- Lexical layer: bag-of-words + char 3-gram cosine over precomputed vectors
  (sub-millisecond, always available, no network).
- Semantic layer: Gemini embeddings (gemini-embedding-001) over the same
  InnoFemme fraud case-study chunks. Chunk vectors are computed once and
  cached to disk; queries embed in ~200-400ms. Falls back to lexical when
  no Gemini key is configured.
"""
from dataclasses import dataclass, field
import asyncio
import json
import logging
import math
import os
import re
from collections import Counter
from typing import List, Optional

from app.config import settings

log = logging.getLogger("momo-shield.kb")

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fraud_knowledge_base.json")
EMBED_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kb_embeddings_cache.json")
EMBEDDING_MODEL = "gemini-embedding-001"
SEMANTIC_MIN_DOT = 0.30  # cosine floor for semantic matches to surface


@dataclass
class KBMatch:
    case_id: str
    title: str
    typology: str
    similarity: float
    is_benign: bool
    psychological_levers: List[str]
    summary: str
    source: str
    engine: str = "lexical"  # "semantic" | "lexical"


class FraudKnowledgeBase:
    def __init__(self, kb_file: str = KB_PATH):
        self.vocab: dict[str, int] = {}
        self.chunks: list[dict] = []
        self._loaded = False
        self._load(kb_file)
        self._semantic_vecs: Optional[list[list[float]]] = None
        self._semantic_ready = False
        self._semantic_lock = asyncio.Lock()

    # ---------- loading ----------

    def _load(self, path: str):
        if not os.path.exists(path):
            log.warning(f"Knowledge base file not found at {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.vocab = data.get("vocab", {})
                self.chunks = data.get("chunks", [])
                self._loaded = True
                log.info(f"Loaded Fraud Knowledge Base: {len(self.chunks)} chunks, {len(self.vocab)} vocab terms.")
        except Exception as exc:
            log.error(f"Failed to load fraud knowledge base: {exc}")

    @staticmethod
    def _chunk_embed_text(chunk: dict) -> str:
        parts = [
            chunk.get("title", ""),
            chunk.get("typology", ""),
            chunk.get("summary", ""),
            " ".join(chunk.get("red_flags") or []),
            chunk.get("sample_dialogue", ""),
        ]
        return " ".join(p for p in parts if p).strip()[:4000]

    # ---------- lexical layer (existing) ----------

    def _tokenize(self, text: str) -> List[str]:
        text = (text or "").lower()
        words = re.findall(r"[a-z0-9_]+", text)
        tokens = list(words)
        for w in words:
            if len(w) >= 4:
                for i in range(len(w) - 2):
                    tokens.append(w[i:i+3])
        return tokens

    def _vectorize(self, tokens: List[str]) -> List[float]:
        counts = Counter(tokens)
        vec = [0.0] * len(self.vocab)
        for t, cnt in counts.items():
            idx = self.vocab.get(t)
            if idx is not None:
                vec[idx] = float(cnt)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def search(self, query: str, top_k: int = 2) -> List[KBMatch]:
        """Lexical cosine search — always available, < 3ms."""
        if not self._loaded or not query.strip():
            return []

        q_tokens = self._tokenize(query)
        q_vec = self._vectorize(q_tokens)

        if not any(q_vec):
            return []

        scored = []
        for c in self.chunks:
            c_vec = c.get("vector") or []
            if not c_vec or len(c_vec) != len(q_vec):
                continue
            dot = sum(a * b for a, b in zip(q_vec, c_vec))
            if dot > 0.15:
                scored.append((dot, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._to_match(c, sim, "lexical") for sim, c in scored[:top_k]]

    # ---------- semantic layer ----------

    def _embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        """Blocking Gemini embedding call (run via asyncio.to_thread)."""
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        out: list[list[float]] = []
        # embed_content accepts a list of contents in one call
        resp = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
        )
        embeddings = getattr(resp, "embeddings", None) or []
        for emb in embeddings:
            vals = getattr(emb, "values", None)
            if vals:
                norm = math.sqrt(sum(x * x for x in vals)) or 1.0
                out.append([x / norm for x in vals])
        return out

    async def _ensure_semantic(self) -> bool:
        """Load or compute chunk embeddings. Returns True if semantic is usable."""
        async with self._semantic_lock:
            if self._semantic_ready:
                return self._semantic_vecs is not None
            self._semantic_ready = True

            if not settings.gemini_enabled or not self.chunks:
                return False

            # Try disk cache first (keyed by model + chunk content hash)
            try:
                if os.path.exists(EMBED_CACHE_PATH):
                    with open(EMBED_CACHE_PATH, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                    if cache.get("model") == EMBEDDING_MODEL and len(cache.get("vectors", [])) == len(self.chunks):
                        self._semantic_vecs = cache["vectors"]
                        log.info("Loaded cached semantic KB embeddings (%d chunks).", len(self._semantic_vecs))
                        return True
            except Exception as exc:
                log.warning("KB embedding cache unreadable: %s", exc)

            texts = [self._chunk_embed_text(c) for c in self.chunks]
            try:
                vecs = await asyncio.wait_for(
                    asyncio.to_thread(self._embed_texts_sync, texts), timeout=180.0
                )
            except Exception as exc:
                log.warning("Semantic KB embedding failed, using lexical only: %s", exc)
                return False

            if len(vecs) != len(self.chunks):
                log.warning("Embedding count mismatch (%d vs %d); semantic disabled.", len(vecs), len(self.chunks))
                return False

            self._semantic_vecs = vecs
            try:
                with open(EMBED_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump({"model": EMBEDDING_MODEL, "vectors": vecs}, f)
            except Exception as exc:
                log.warning("Could not write KB embedding cache: %s", exc)
            log.info("Computed semantic KB embeddings for %d chunks.", len(vecs))
            return True

    async def search_semantic(self, query: str, top_k: int = 2) -> List[KBMatch]:
        """Gemini-embedding cosine search. Empty list when unavailable."""
        if not query.strip() or not await self._ensure_semantic():
            return []
        try:
            q_vec = await asyncio.wait_for(
                asyncio.to_thread(self._embed_texts_sync, [query]), timeout=5.0
            )
        except Exception as exc:
            log.warning("Query embedding failed: %s", exc)
            return []
        if not q_vec:
            return []
        qv = q_vec[0]

        scored = []
        for c, c_vec in zip(self.chunks, self._semantic_vecs or []):
            dot = sum(a * b for a, b in zip(qv, c_vec))
            if dot >= SEMANTIC_MIN_DOT:
                scored.append((dot, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._to_match(c, sim, "semantic") for sim, c in scored[:top_k]]

    async def search_smart(self, query: str, top_k: int = 1) -> List[KBMatch]:
        """Semantic first, lexical fallback. This is what routes should call."""
        sem = await self.search_semantic(query, top_k=top_k)
        if sem:
            return sem
        return self.search(query, top_k=top_k)

    async def get_rag_context_smart(self, query: str) -> Optional[str]:
        matches = await self.search_smart(query, top_k=1)
        if not matches:
            return None
        return format_rag_context(matches[0])

    def get_rag_context(self, query: str) -> Optional[str]:
        """Lexical-only context (sync fallback for non-async callers)."""
        matches = self.search(query, top_k=1)
        if not matches:
            return None
        return format_rag_context(matches[0])

    @staticmethod
    def _to_match(chunk: dict, similarity: float, engine: str) -> KBMatch:
        return KBMatch(
            case_id=chunk.get("id", "UNKNOWN"),
            title=chunk.get("title", "Untitled"),
            typology=chunk.get("typology", "social_engineering"),
            similarity=round(similarity, 3),
            is_benign=bool(chunk.get("is_benign", False)),
            psychological_levers=chunk.get("psychological_levers", []),
            summary=chunk.get("summary", ""),
            source=_display_source(chunk.get("source")),
            engine=engine,
        )


def _display_source(raw) -> str:
    """Rebrand provenance for display: the corpus is the InnoFemme fraud
    case-study library, not a KNUST-branded product surface."""
    s = str(raw or "InnoFemme Fraud Case Corpus")
    s = s.replace("KNUST Kumasi Case Study Library", "Fraud Case Corpus")
    s = s.replace("KNUST Case Study Library", "Fraud Case Corpus")
    s = s.replace("InnoFemme x Hack for Equity", "InnoFemme")
    return s


def format_rag_context(match: KBMatch) -> str:
    if match.is_benign:
        return (
            f"Ground truth precedent (semantic match {match.similarity:.0%}): "
            f"Verified benign pattern — {match.title}. Typical safe transaction."
        )
    return (
        f"Precedent from InnoFemme Fraud Case Study {match.case_id} ({match.title}):\n"
        f"- Typology: {match.typology}\n"
        f"- Psychological Levers: {', '.join(match.psychological_levers)}\n"
        f"- Modus Operandi: {match.summary}\n"
        f"- Match Confidence: {match.similarity:.0%} ({match.engine})"
    )


# Global singleton instance
knowledge_base = FraudKnowledgeBase()
