from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "production" turns on validate_for_production()'s checks at startup (see
    # main.py's lifespan) - every other setting below stays dev-friendly by default
    # so local setup never needs more than a couple of env vars.
    environment: Literal["development", "production"] = "development"

    database_url: str = ""

    secret_key: str = _DEFAULT_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    gemini_api_key: str = ""
    ai_model_ledger_prediction: str = "gemini-2.5-pro"
    ai_batch_size: int = 40
    ai_auto_accept_threshold: int = 90
    ai_new_ledger_confidence_cap: int = 85
    ai_max_ledger_context: int = 150

    cors_origins: str = "http://localhost:5173"

    # "local" writes to local disk - fine for a single long-lived dev machine, but
    # Cloud Run containers are ephemeral and don't share a filesystem across
    # instances, so production must use "gcs".
    storage_backend: str = "local"
    storage_dir: str = "storage/uploads"
    gcs_bucket_name: str = ""
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

    def validate_for_production(self) -> list[str]:
        """Config problems that must be fixed before this is safe to run in
        production. Empty when `environment != "production"` - dev/test never fail
        on these, since e.g. SQLite and local disk storage are the intended dev
        setup, not a mistake.
        """
        if self.environment != "production":
            return []

        problems: list[str] = []
        if self.secret_key == _DEFAULT_SECRET_KEY or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be overridden with a long random value.")
        if not self.database_url:
            problems.append("DATABASE_URL must be set.")
        elif self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must not be SQLite - use Cloud SQL Postgres.")
        if not self.gemini_api_key:
            problems.append("GEMINI_API_KEY must be set (the AI prediction stage requires it).")
        if self.storage_backend != "gcs":
            problems.append(
                "STORAGE_BACKEND must be 'gcs' - local disk doesn't persist or share across "
                "Cloud Run instances."
            )
        elif not self.gcs_bucket_name:
            problems.append("GCS_BUCKET_NAME must be set when STORAGE_BACKEND=gcs.")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origin_list):
            problems.append("CORS_ORIGINS still points at localhost - set it to the deployed frontend URL.")
        if self.run_worker_in_process:
            problems.append(
                "RUN_WORKER_IN_PROCESS should be false - run the worker as its own "
                "always-on Cloud Run service instead (see DEPLOY.md)."
            )
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
