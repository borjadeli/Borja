"""SQLite connection y session factory."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings


def _build_engine() -> Engine:
    settings = get_settings()
    db_file = Path(settings.db_url.replace("sqlite:///", ""))
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        settings.db_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        echo=False,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Crea tablas si no existen. Llamar al arranque."""
    from backend import models  # noqa: F401  (registra metadata)
    from backend import panic  # noqa: F401  (registra SystemConfig)
    from backend.models import Base

    Base.metadata.create_all(bind=engine)
