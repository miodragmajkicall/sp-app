import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set via backend/.env")

# Stabilna konekcija (pre-ping) i razuman isolation level
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    isolation_level="READ COMMITTED",
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_session() -> Session:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def db_ping() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
