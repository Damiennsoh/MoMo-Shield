from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    glance_api_key: str = ""
    glance_base_url: str = "https://api.glance.rancardmobility.com/v1"
    
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_seconds: float = 15.0
    
    sandbox_api_key: str = ""
    sandbox_team_key: str = ""
    sandbox_client_id: str = ""
    sandbox_network_client_id: str = ""
    sandbox_network_api_key: str = ""
    sandbox_base_url: str = "https://hackathon.innofemme.org/api/w"
    plugin_lookup_timeout_seconds: float = 1.0

    # MTN MoMo Collection API: keep credentials on the backend only.
    mtn_momo_base_url: str = "https://sandbox.momodeveloper.mtn.com"
    mtn_momo_api_user: str = ""
    mtn_momo_api_key: str = ""
    mtn_momo_subscription_key: str = ""
    mtn_momo_callback_url: str = ""
    mtn_momo_request_api_key: str = ""

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
