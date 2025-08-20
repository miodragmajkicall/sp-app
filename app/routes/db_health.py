from fastapi import APIRouter, HTTPException
from app import db as dbmod  # očekuje se da postoji db.ping()

router = APIRouter(tags=["health"])

@router.get("/db/health")
def db_health():
    """
    Provjera konekcije prema bazi.
    Vraća 200 ako db.ping() uspije, inače 503.
    """
    try:
        ping_fn = getattr(dbmod, "ping", None)
        if callable(ping_fn) and ping_fn():
            return {"status": "ok", "db": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db error: {e!r}")
    raise HTTPException(status_code=503, detail="db not reachable")
