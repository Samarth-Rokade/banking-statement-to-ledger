from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = ""

    secret_key: str = "change-me-to-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    gemini_api_key: str = ""
    ai_model_ledger_prediction: str = "gemini-2.5-pro"
    ai_batch_size: int = 40
    ai_auto_accept_threshold: int = 90
    ai_new_ledger_confidence_cap: int = 85
    ai_max_ledger_context: int = 150

    cors_origins: str = "http://localhost:5173"

    storage_dir: str = "storage/uploads"
    max_upload_size_bytes: int = 20 * 1024 * 1024  # 20 MB

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
