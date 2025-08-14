from fastapi import FastAPI
from .config import settings
from .db import ping
from .routes import tenants as tenants_routes
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",  # Vite/React
        "http://localhost:3000", "http://127.0.0.1:3000",  # CRA/Next
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
    try:
        ok = ping()
        return {"db": "ok" if ok else "fail"}
    except Exception as e:
        return {"db": "fail", "error": str(e)}
    
app.include_router(tenants_routes.router)

