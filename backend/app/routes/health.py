from fastapi import APIRouter
from app.db import db_ping

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/db/health")
def db_health():
    # samo ping; test očekuje baš {"db": "ok"}
    db_ping()
    return {"db": "ok"}
