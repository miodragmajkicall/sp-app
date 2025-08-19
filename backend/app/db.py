# backend/app/db.py
import os
from typing import Optional, Generator

from fastapi import Header
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# DATABASE_URL iz env-a ili default iz docker-compose-a
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://sp_app:sp_app@db:5432/sp_app",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_session(
    tenant_code: Optional[str] = Header(
        default=None,
        alias="X-Tenant-Code",
        convert_underscores=False,
    )
) -> Generator[Session, None, None]:
    """
    FastAPI dependency: otvara DB session i, ako je prosleđen X-Tenant-Code,
    postavlja search_path na '<tenant_code>, public'.
    """
    db = SessionLocal()
    try:
        if tenant_code:
            db.execute(text("SET search_path TO :schema, public"), {"schema": tenant_code})
        yield db
    finally:
        db.close()


# Legacy alias (ako negdje postoji stari import get_db)
def get_db(
    tenant_code: Optional[str] = Header(
        default=None,
        alias="X-Tenant-Code",
        convert_underscores=False,
    )
) -> Generator[Session, None, None]:
    yield from get_session(tenant_code)


def ping() -> bool:
    """Jednostavan DB health check (koristi se u /health)."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
