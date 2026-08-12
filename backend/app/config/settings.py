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

    # Runs the job worker loop in a background thread of the API process itself, so
    # one `uvicorn` process is enough in dev - no second terminal needed. Turn this
    # off for a real deployment where the worker runs as its own process/replica
    # (e.g. once on Postgres with multiple API instances, so jobs aren't claimed
    # redundantly and worker scaling is independent of API scaling).
    run_worker_in_process: bool = True
    worker_poll_interval_seconds: float = 2.0

    # Module 15 (Export): the ledger representing the bank account each statement
    # belongs to - every voucher's other leg. v1 assumption: one bank ledger for the
    # whole system; multi-account support (a bank ledger per uploaded file) is a
    # flagged future enhancement, not needed by any statement seen so far.
    tally_bank_ledger_name: str = "Bank Account"
    # Optional - if set, stamped into the XML so Tally imports straight into this
    # company; if blank, Tally imports into whichever company is currently open.
    tally_company_name: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
