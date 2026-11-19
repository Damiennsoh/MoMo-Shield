from fastapi import APIRouter, HTTPException, Query, Request
from app.models.events import AssessRequest, CaseReferenceRequest
from app.models.responses import AssessResponse
from app.engine.scorer import assess
from app.engine.state import global_window
from app.config import settings
from app.ai.gemini_client import extract_intent
from app.ai.transcription import transcribe_wav
from app.knowledge.case_reference import case_reference as run_case_reference
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()
MAX_TRANSCRIPTION_BYTES = 8 * 1024 * 1024

@router.post("/gemini/healthcheck")
async def gemini_healthcheck():
    """Make a real, minimal Gemini request to verify configured credentials/model."""
    if not settings.gemini_enabled:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_configured", "message": "Set GEMINI_API_KEY in backend/.env and restart the backend."},
        )
    try:
        result = await extract_intent("Connectivity test: the meeting starts at noon.")
        if not isinstance(result, dict) or "evidence_phrases" not in result:
            raise RuntimeError("Gemini returned an unexpected response shape")
        return {"status": "ok", "model": settings.gemini_model, "message": "Gemini API request succeeded."}
    except Exception as exc:
        log.warning("Gemini connectivity check failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "model": settings.gemini_model,
                    "message": "Gemini request failed. Check the API key, model access, network, and backend logs."},
        ) from exc

@router.post("/assess", response_model=AssessResponse)
async def assess_event(req: AssessRequest):
    try:
        result = await assess(req.event)
        log.info(f"Assessed event {result.event_id}: score={result.risk_score} tier={result.risk_tier}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal assessment error")

@router.post("/transcribe")
async def transcribe_audio(
    request: Request,
    language_hint: str = Query(default="English", max_length=48),
):
    """Transcribe a short consented synthetic WAV; never persist or log its bytes."""
    if not settings.gemini_enabled:
        raise HTTPException(
            status_code=503,
            detail="Speech transcription is not configured on this backend.",
        )
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"audio/wav", "audio/x-wav", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a WAV recording only.")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="Recording exceeds the 8 MB demo limit.")
    chunks = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_TRANSCRIPTION_BYTES:
            raise HTTPException(status_code=413, detail="Recording exceeds the 8 MB demo limit.")
        chunks.append(chunk)
    raw_audio = b"".join(chunks)
    if len(raw_audio) < 12 or raw_audio[:4] != b"RIFF" or raw_audio[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The recording is not a valid WAV file.")
    try:
        return await transcribe_wav(raw_audio, language_hint)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        log.warning("Transcription request failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Transcription service is unavailable.") from exc

@router.post("/case-reference")
async def retrieve_case_reference(req: CaseReferenceRequest):
    """Return optional retrieved case context; never feed it into the scoring rules."""
    if not settings.gemini_enabled:
        raise HTTPException(
            status_code=503,
            detail="Case reference needs a configured Gemini API key; the primary assessment remains available without it.",
        )
    try:
        return await run_case_reference(req.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.post("/reset")
async def reset_state():
    global_window.reset()
    return {"status": "ok"}
