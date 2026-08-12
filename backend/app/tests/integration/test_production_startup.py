import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import app


@pytest.fixture()
def _restore_environment():
    settings = get_settings()
    original = settings.environment
    yield settings
    settings.environment = original


def test_app_refuses_to_start_in_production_with_dev_config(_restore_environment):
    _restore_environment.environment = "production"
    with pytest.raises(RuntimeError, match="Refusing to start in production"):
        with TestClient(app):
            pass
