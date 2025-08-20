# backend/app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import tenants as tenants_routes
from .routes import cash as cash_routes

app = FastAPI(title=settings.PROJECT_NAME)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plain health
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

# DB health (inline, bez dodatnih paketa/uvoza routera)
@app.get("/db/health", tags=["health"])
def db_health():
    """
    Provjera konekcije prema bazi.
    Vraća 200 ako db.ping() uspije, inače 503.
    """
    try:
        # Lazy import da izbjegnemo ciklične uvoze
        from app import db as dbmod
        ping_fn = getattr(dbmod, "ping", None)
        if callable(ping_fn) and ping_fn():
            return {"status": "ok", "db": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db error: {e!r}")
    raise HTTPException(status_code=503, detail="db not reachable")

# Routers
app.include_router(tenants_routes.router)
app.include_router(cash_routes.router)
