import type {
  Assessment,
  HandsetEvent,
  HealthResponse,
  SandboxEvent,
} from "./types";

const BACKEND = () =>
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Demo-device bearer token: env for the dashboard, #token= fragment for /handset. */
export function demoToken(): string {
  if (typeof window !== "undefined") {
    const hash = window.location.hash;
    if (hash.startsWith("#token=")) return decodeURIComponent(hash.slice(7));
  }
  return process.env.NEXT_PUBLIC_DEMO_DEVICE_TOKEN ?? "";
}

const ASSESS_TIMEOUT_MS = 18_000;

async function request<T>(path: string, init?: RequestInit, timeoutMs = 8_000): Promise<T> {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BACKEND()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json())?.detail ?? ""; } catch { /* ignore */ }
      throw new Error(detail || `HTTP ${res.status} on ${path}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

/* ---------- response normalization ---------- */

interface RawRule { rule_id?: string; description?: string; points?: number }
interface RawIntent {
  pattern?: string | null;
  evidence_phrases?: string[];
  requested_secret?: string | null;
  language_detected?: string | null;
  suggested_warning?: string | null;
}
interface RawAssessment {
  msisdn: string;
  risk_score: number;
  risk_tier: string;
  triggered_rules: (RawRule | string)[];
  llm_extracted_intent?: RawIntent | string | null;
  llm_unavailable?: boolean;
  intent_source?: string;
  recommended_action: string;
  twi_warning_message?: string | null;
  english_warning_message?: string | null;
  intervention_category?: string | null;
  intervention_title?: string | null;
  intervention_message?: string | null;
  event_id?: string;
  timestamp?: string;
}

function normalizeAssessment(raw: RawAssessment, latencyMs: number): Assessment {
  const rules = (raw.triggered_rules ?? []).map((r) =>
    typeof r === "string" ? r : `${r.description ?? r.rule_id ?? "rule"} (+${r.points ?? 0})`
  );
  const intent =
    raw.llm_extracted_intent && typeof raw.llm_extracted_intent === "object"
      ? {
          lever: raw.llm_extracted_intent.pattern ?? undefined,
          requested_secret: raw.llm_extracted_intent.requested_secret ?? null,
          evidence: raw.llm_extracted_intent.evidence_phrases ?? [],
          language_detected: raw.llm_extracted_intent.language_detected ?? undefined,
          suggested_warning: raw.llm_extracted_intent.suggested_warning ?? undefined,
        }
      : null;
  return {
    msisdn: raw.msisdn,
    risk_score: raw.risk_score,
    risk_tier: raw.risk_tier as Assessment["risk_tier"],
    triggered_rules: rules,
    llm_extracted_intent: intent,
    llm_unavailable: raw.llm_unavailable ?? false,
    intent_source: raw.intent_source ?? "none",
    recommended_action: raw.recommended_action as Assessment["recommended_action"],
    twi_warning_message: raw.twi_warning_message ?? null,
    english_warning_message: raw.english_warning_message ?? null,
    intervention_title: raw.intervention_title ?? null,
    intervention_message: raw.intervention_message ?? null,
    guidance:
      raw.intervention_message ??
      raw.english_warning_message ??
      raw.twi_warning_message ??
      undefined,
    source: "backend",
    latency_ms: Math.round(latencyMs),
    timestamp: raw.timestamp,
  };
}

/* ---------- handset event mapping (component model <-> backend schema) ---------- */

/** Translate the UI-friendly HandsetEvent into the backend DemoDeviceEvent schema. */
export function toBackendEvent(evt: HandsetEvent): Record<string, unknown> {
  switch (evt.type) {
    case "sms":
      return {
        type: "sms",
        scenario: evt.scenario ?? "Live Signal Lab",
        caller: evt.from ?? evt.caller ?? "Unknown sender",
        message: evt.body ?? evt.message ?? "",
        event_key: evt.event_key,
        sip_message: evt.sip_message,
      };
    case "call":
      return {
        type: "call",
        scenario: evt.scenario ?? "Live Signal Lab",
        caller: evt.from ?? evt.caller ?? "Unknown caller",
        status: evt.status ?? "Incoming call",
        transcript: evt.transcript,
        event_key: evt.event_key,
        trigger_sip: evt.trigger_sip,
        sip_hangup: evt.sip_hangup,
      };
    case "call_status":
      // Backend has no call_status type; publish as a call card update.
      return {
        type: "call",
        scenario: evt.scenario ?? "Live Signal Lab",
        caller: evt.from ?? "Unknown caller",
        status: evt.status ?? "",
        event_key: evt.event_key,
      };
    case "warning":
      return {
        type: "warning",
        scenario: evt.scenario ?? "Live Signal Lab",
        warning: evt.text_twi || evt.text || "",
        warning_english: evt.text ?? "",
        event_key: evt.event_key,
        suppress_audio: evt.suppress_audio,
        sip_hangup: evt.sip_hangup,
      };
    case "reset":
      return { type: "reset", scenario: evt.scenario ?? "Live Signal Lab" };
    default:
      return { type: "screen", message: evt.status ?? "", scenario: evt.scenario };
  }
}

/** Translate a raw backend demo-device event into the UI HandsetEvent shape. */
export function fromBackendEvent(raw: Record<string, unknown>): HandsetEvent | null {
  const type = String(raw.type ?? "");
  const status = String(raw.status ?? "");
  switch (type) {
    case "sms":
      return {
        type: "sms",
        from: String(raw.caller ?? "Unknown sender"),
        body: String(raw.message ?? ""),
        scenario: raw.scenario as string | undefined,
      };
    case "call": {
      const s = status.toLowerCase();
      if (/ended|declined|missed|completed/.test(s)) {
        return { type: "call_status", status: "ended", scenario: raw.scenario as string | undefined };
      }
      if (/in progress|ongoing|no intervention|cooling-off/.test(s)) {
        return { type: "call_status", status, scenario: raw.scenario as string | undefined };
      }
      return {
        type: "call",
        from: String(raw.caller ?? "Unknown caller"),
        status: /incoming|ringing/.test(s) ? "ringing" : s || "ringing",
        direction: "incoming",
        transcript: raw.transcript ? String(raw.transcript) : undefined,
        sip_managed: Boolean(raw.sip_managed),
        force_browser_ring: Boolean(raw.force_browser_ring),
        scenario: raw.scenario as string | undefined,
      };
    }
    case "warning":
      return {
        type: "warning",
        title: "SAFETY GUIDANCE · SYNTHETIC DEMO",
        text: String(raw.warning_english || raw.warning || raw.message || ""),
        text_twi: raw.warning && raw.warning !== raw.warning_english ? String(raw.warning) : undefined,
        level: "HIGH",
        sip_hangup: Boolean(raw.sip_hangup),
        suppress_audio: Boolean(raw.suppress_audio),
        scenario: raw.scenario as string | undefined,
      };
    case "reset":
      return { type: "reset", scenario: raw.scenario as string | undefined };
    case "screen":
      return { type: "screen", status: String(raw.message ?? raw.status ?? "") };
    default:
      return null;
  }
}

/* ---------- public API ---------- */

export const api = {
  health: () => request<HealthResponse>("/health"),

  geminiHealth: async () => {
    const r = await request<{ status?: string; model?: string; message?: string }>(
      "/api/v1/gemini/healthcheck",
      { method: "POST" }
    );
    return { ok: r.status === "ok", detail: r.message, model: r.model };
  },

  assess: async (event: SandboxEvent): Promise<Assessment> => {
    const started = performance.now();
    const raw = await request<RawAssessment>(
      "/api/v1/assess",
      { method: "POST", body: JSON.stringify({ event }) },
      ASSESS_TIMEOUT_MS
    );
    return normalizeAssessment(raw, performance.now() - started);
  },

  reset: () => request<{ ok: true }>("/api/v1/reset", { method: "POST" }),

  /** Backend expects a raw WAV body (RIFF/WAVE), not multipart. */
  transcribe: async (wavBlob: Blob, language_hint = "English") => {
    const res = await fetch(
      `${BACKEND()}/api/v1/transcribe?language_hint=${encodeURIComponent(language_hint)}`,
      {
        method: "POST",
        headers: { "Content-Type": "audio/wav" },
        body: wavBlob,
      }
    );
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json())?.detail ?? ""; } catch { /* ignore */ }
      throw new Error(detail || `HTTP ${res.status} on /transcribe`);
    }
    return (await res.json()) as { transcript: string; uncertain?: boolean; note?: string };
  },

  caseReference: async (text: string, language_hint?: string) => {
    const r = await request<Record<string, unknown>>("/api/v1/case-reference", {
      method: "POST",
      body: JSON.stringify({ text, language_hint }),
    });
    const cases = (r.retrieved_cases ?? r.cases ?? []) as Record<string, unknown>[];
    return {
      cases: cases.map((c) => ({
        title: c.title ?? c.case_id ?? "Case",
        similarity: c.retrieval_similarity ?? c.similarity,
        note: c.attack_pattern ?? c.note,
      })),
      note: r.note as string | undefined,
    };
  },

  publishHandset: (evt: HandsetEvent) => {
    const token = demoToken();
    return request<{ status: string; event_id?: number; sip?: unknown }>(
      "/api/v1/demo-device/publish",
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(toBackendEvent(evt)),
      }
    );
  },

  callAction: (action: "answer" | "decline" | "end") => {
    const token = demoToken();
    return request<{ status: string }>("/api/v1/demo-device/call-action", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ action }),
    });
  },
};

/**
 * Connect to the handset SSE stream. EventSource cannot send the required
 * Authorization header, so this uses fetch + a readable stream reader.
 * Returns a cleanup function.
 */
export function streamHandset(onEvent: (evt: HandsetEvent) => void): () => void {
  const token = demoToken();
  const controller = new AbortController();
  let closed = false;

  (async () => {
    try {
      const res = await fetch(`${BACKEND()}/api/v1/demo-device/stream`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!closed) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const line = block.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            const mapped = fromBackendEvent(JSON.parse(line.slice(6)));
            if (mapped) onEvent(mapped);
          } catch { /* ignore malformed frames */ }
        }
      }
    } catch {
      if (!closed) onEvent({ type: "status", status: "disconnected" });
    }
  })();

  return () => {
    closed = true;
    controller.abort();
  };
}

export function tierColor(tier: string): string {
  switch (tier) {
    case "HIGH": return "text-risk-high";
    case "MEDIUM": return "text-risk-medium";
    default: return "text-risk-low";
  }
}

export function tierBar(tier: string): string {
  switch (tier) {
    case "HIGH": return "bg-risk-high";
    case "MEDIUM": return "bg-risk-medium";
    default: return "bg-risk-low";
  }
}

/** Speak an English warning with safe expansions for screen readers. */
export function speakWarning(text: string) {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const safe = text
    .replace(/\bPIN\b/g, "pin")
    .replace(/\bOTP\b/g, "one-time password");
  const utter = new SpeechSynthesisUtterance(safe);
  utter.lang = "en-GH";
  utter.rate = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}
