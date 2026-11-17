from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.api.sandbox import router as sandbox_router
from app.api.demo_device import router as demo_device_router
from app.config import settings
from app.utils.logger import setup_logging

setup_logging()

app = FastAPI(
    title="InnoFemme Track 1 — Fraud Detection Engine",
    version="1.0.0",
    description="Early detection of social engineering in mobile money ecosystems",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1/sandbox")
app.include_router(demo_device_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "track1-fraud-detection", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
