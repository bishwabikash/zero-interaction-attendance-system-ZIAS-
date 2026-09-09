"""Database engine + session factory (lazy)."""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from api.config import settings
from api.db_models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _database_url() -> str:
    return (
        f"mysql+mysqlconnector://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


def _init_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        return
    _engine = create_engine(
        _database_url(),
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


class _EngineProxy:
    """Import-safe stand-in — resolves the real engine on first use."""

    def __getattr__(self, item):
        _init_engine()
        return getattr(_engine, item)


engine = _EngineProxy()


def init_db() -> None:
    _init_engine()
    with _engine.connect() as conn:
        print(f"[db] connected to {settings.DB_NAME}@{settings.DB_HOST}")
    Base.metadata.create_all(bind=_engine)
    print("[db] tables ensured")


def close_db() -> None:
    if _engine is not None:
        _engine.dispose()
        print("[db] closed")


def SessionLocal() -> Session:
    _init_engine()
    return _SessionLocal()  # type: ignore[misc]


@contextmanager
def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
