"""
Real-time Semantic Knowledge Base Matcher (RAG Engine)
Loads precomputed vector embeddings for InnoFemme KNUST Case Study dossiers and Benign Controls.
Performs sub-millisecond (< 3ms) in-memory cosine similarity search over Ghanaian fraud typologies.
"""
from dataclasses import dataclass
import json
import logging
import math
import os
import re
from collections import Counter
from typing import List, Optional

log = logging.getLogger("momo-shield.kb")

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fraud_knowledge_base.json")

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


class FraudKnowledgeBase:
    def __init__(self, kb_file: str = KB_PATH):
        self.vocab: dict[str, int] = {}
        self.chunks: list[dict] = []
        self._loaded = False
        self._load(kb_file)

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
        """Perform in-memory cosine similarity search in < 3ms."""
        if not self._loaded or not query.strip():
            return []

        q_tokens = self._tokenize(query)
        q_vec = self._vectorize(q_tokens)
        
        # Check if vector has non-zero magnitude
        if not any(q_vec):
            return []

        scored = []
        for c in self.chunks:
            c_vec = c.get("vector") or []
            if not c_vec or len(c_vec) != len(q_vec):
                continue
            # Cosine similarity of two unit-normalized vectors is the dot product
            dot = sum(a * b for a, b in zip(q_vec, c_vec))
            if dot > 0.15:  # meaningful correlation threshold
                scored.append((dot, c))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, c in scored[:top_k]:
            results.append(
                KBMatch(
                    case_id=c.get("id", "UNKNOWN"),
                    title=c.get("title", "Untitled"),
                    typology=c.get("typology", "social_engineering"),
                    similarity=round(sim, 3),
                    is_benign=bool(c.get("is_benign", False)),
                    psychological_levers=c.get("psychological_levers", []),
                    summary=c.get("summary", ""),
                    source=c.get("source", "InnoFemme Case Study Library"),
                )
            )
        return results

    def get_rag_context(self, query: str) -> Optional[str]:
        """Generate grounded RAG context for Gemini inference."""
        matches = self.search(query, top_k=1)
        if not matches:
            return None
        top = matches[0]
        if top.is_benign:
            return f"Ground truth precedent: Verified benign pattern ({top.title}). Typical safe transaction."
        return (
            f"Precedent from InnoFemme KNUST Case Study {top.case_id} ({top.title}):\n"
            f"- Typology: {top.typology}\n"
            f"- Psychological Levers: {', '.join(top.psychological_levers)}\n"
            f"- Modus Operandi: {top.summary}\n"
            f"- Historical Similarity: {top.similarity:.0%}"
        )


# Global singleton instance
knowledge_base = FraudKnowledgeBase()
