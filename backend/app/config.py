from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_seconds: int = 3
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: List[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]
    risk_threshold_medium: int = 40
    risk_threshold_high: int = 75

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key) and self.gemini_api_key != "your_gemini_api_key_here"

settings = Settings()
