from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import get_settings

settings = get_settings()

# Engine creation is deferred until DATABASE_URL is actually set (empty string is a
# valid state pre-DB-provisioning) so importing this module never fails.
engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in backend/.env before using the database."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
