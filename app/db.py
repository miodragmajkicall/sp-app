from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# DATABASE_URL npr: postgresql+psycopg2://user:pass@db:5432/app
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/postgres",
)

# echo=False da ne spamuje logove; po želji uključi
engine = create_engine(DATABASE_URL, echo=False, future=True)

# autoflush=False i autocommit=False su standardni defaulti
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency: vrati *Session* (ne contextmanager).
    FastAPI će korektno pozvati finally blok; ovdje radimo commit/rollback.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
