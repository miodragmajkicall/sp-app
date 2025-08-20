from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import ping
from .routes import tenants as tenants_routes
from .routes import cash as cash_routes  # novo
from app.routes.db_health import router as db_health_router



app = FastAPI(title=settings.PROJECT_NAME)

from .routes import cash as cash_routes
app.include_router(cash_routes.router)
app.include_router(db_health_router)




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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db/health")
def db_health():
    ping()
    return {"db": "ok"}

# Routers – OVO MORA BITI POSLIJE kreiranja app-a:
app.include_router(tenants_routes.router)
app.include_router(cash_routes.router)

