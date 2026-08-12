import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import get_settings
from app.database import Base, get_db
from app.main import app
from app.models.voucher_type import VoucherType

# Mirrors migration 0013's seed data - voucher_types is small, fixed reference data
# (like an enum) that VoucherGenerator always depends on, unlike ledger_groups/ledgers
# which individual tests deliberately seed themselves.
_VOUCHER_TYPES = ["Receipt", "Payment", "Contra", "Journal"]


@pytest.fixture(autouse=True)
def _disable_in_process_worker():
    """The `client` fixture's TestClient triggers app startup/shutdown, which would
    otherwise spin up the real in-process worker (app/main.py's lifespan) against
    the actual configured DATABASE_URL - not the test's isolated in-memory session -
    silently touching real data. Every test gets this off by default.
    """
    settings = get_settings()
    original = settings.run_worker_in_process
    settings.run_worker_in_process = False
    yield
    settings.run_worker_in_process = original


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    session = TestingSessionLocal()
    session.add_all([VoucherType(name=name) for name in _VOUCHER_TYPES])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
