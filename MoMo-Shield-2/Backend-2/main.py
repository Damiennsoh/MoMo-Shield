import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.config import settings
from app.utils.logger import setup_logging

setup_logging()

app = FastAPI(
    title="MoMo Shield Intelligence Core",
    version="2.0.0",
    description="Enterprise Fraud Middleware for InnoFemme Sandbox & Rancard Glance",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def warm_engines():
    """Pre-load heavy optional engines so the first scored event doesn't
    pay cold-start latency. All fail-open: a missing model or embedding
    cache degrades gracefully, never blocks startup."""
    import asyncio
    from app.engine.kb import knowledge_base
    from app.integrations import ml_scorer

    await asyncio.to_thread(ml_scorer._load)
    try:
        # Pre-load cached chunk embeddings so the first plug-in SMS pays
        # only the ~300ms query-embed, not a cold cache build.
        await asyncio.wait_for(knowledge_base._ensure_semantic(), timeout=30)
    except Exception:
        pass  # semantic KB degrades to lexical — never blocks startup


@app.get("/health")
async def health():
    return {"status": "operational", "middleware": "MoMo Shield v2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
