from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    glance_api_key: str = ""
    glance_base_url: str = "https://api.glance.rancardmobility.com/v1"
    
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    
    sandbox_api_key: str = ""
    sandbox_base_url: str = "https://api.innofemme-sandbox.com/v1"

    # Inbound webhook auth: when set, POST /webhook/sandbox requires
    # "Authorization: Bearer <webhook_api_key>". Empty = open (dev sandbox).
    webhook_api_key: str = ""

    # Comma-separated allowed frontend origins. "*" for local dev only.
    cors_origins: str = "*"
    
    risk_threshold_high: int = 75
    risk_threshold_medium: int = 40

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    @property
    def glance_enabled(self) -> bool:
        return bool(self.glance_api_key) and "your_" not in self.glance_api_key

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key) and "your_" not in self.gemini_api_key

settings = Settings()