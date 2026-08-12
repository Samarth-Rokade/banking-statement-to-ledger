from app.config.settings import Settings

_GOOD_PROD_KWARGS = dict(
    environment="production",
    secret_key="x" * 40,
    database_url="postgresql+psycopg://user:pass@/db?host=/cloudsql/proj:region:instance",
    gemini_api_key="real-key",
    storage_backend="gcs",
    gcs_bucket_name="my-bucket",
    cors_origins="https://app.example.com",
    run_worker_in_process=False,
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_development_settings_never_flag_problems():
    # Defaults (SQLite, local storage, localhost CORS) are the intended dev setup,
    # not a misconfiguration - validate_for_production() must stay silent unless
    # environment is actually "production".
    settings = _settings()
    assert settings.environment == "development"
    assert settings.validate_for_production() == []


def test_fully_correct_production_settings_pass():
    assert _settings(**_GOOD_PROD_KWARGS).validate_for_production() == []


def test_default_secret_key_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "secret_key": "change-me-to-a-long-random-string"}
    problems = _settings(**kwargs).validate_for_production()
    assert any("SECRET_KEY" in p for p in problems)


def test_short_secret_key_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "secret_key": "too-short"}
    problems = _settings(**kwargs).validate_for_production()
    assert any("SECRET_KEY" in p for p in problems)


def test_sqlite_database_url_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "database_url": "sqlite:///./bank.db"}
    problems = _settings(**kwargs).validate_for_production()
    assert any("SQLite" in p for p in problems)


def test_missing_database_url_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "database_url": ""}
    problems = _settings(**kwargs).validate_for_production()
    assert any("DATABASE_URL must be set" in p for p in problems)


def test_missing_gemini_key_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "gemini_api_key": ""}
    problems = _settings(**kwargs).validate_for_production()
    assert any("GEMINI_API_KEY" in p for p in problems)


def test_local_storage_backend_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "storage_backend": "local"}
    problems = _settings(**kwargs).validate_for_production()
    assert any("STORAGE_BACKEND" in p for p in problems)


def test_gcs_backend_without_bucket_name_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "gcs_bucket_name": ""}
    problems = _settings(**kwargs).validate_for_production()
    assert any("GCS_BUCKET_NAME" in p for p in problems)


def test_localhost_cors_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "cors_origins": "http://localhost:5173"}
    problems = _settings(**kwargs).validate_for_production()
    assert any("CORS_ORIGINS" in p for p in problems)


def test_in_process_worker_is_rejected_in_production():
    kwargs = {**_GOOD_PROD_KWARGS, "run_worker_in_process": True}
    problems = _settings(**kwargs).validate_for_production()
    assert any("RUN_WORKER_IN_PROCESS" in p for p in problems)
