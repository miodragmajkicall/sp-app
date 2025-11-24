from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# --- SIMPLE SETTINGS (ENV via docker-compose) ---
#   DATABASE_URL=postgresql+psycopg2://sp_app:sp_app@db:5432/sp_app
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://sp_app:sp_app@db:5432/sp_app")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yield SQLAlchemy session (public schema)."""
    db: Session = SessionLocal()
    try:
        # Osigurajmo da je 'public' aktivan (bez obzira na nešto ranije).
        db.execute(text("SET search_path TO public"))
        yield db
    finally:
        db.close()
