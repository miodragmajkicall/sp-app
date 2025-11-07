from __future__ import annotations

import os
from fastapi import APIRouter
from app.db import db_ping

router = APIRouter(prefix="/debug", tags=["debug"])

def _mask_db_url(url: str | None) -> str:
    if not url:
        return ""
    # postgresql+psycopg2://user:pass@host:5432/db
    try:
        prefix, rest = url.split("://", 1)
        creds, tail = rest.split("@", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            masked = f"{user}:****"
        else:
            masked = creds  # no password in URL
        return f"{prefix}://{masked}@{tail}"
    except Exception:
        return "***"

@router.get("/health")
def health():
    ok = db_ping()
    return {"status": "ok" if ok else "fail"}

@router.get("/config")
def config():
    raw = os.getenv("DATABASE_URL")
    return {
        "database_url": _mask_db_url(raw),
        "env": "container",
    }
