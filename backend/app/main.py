from fastapi import FastAPI
from .config import settings
from .db import ping
from .routes import tenants as tenants_routes


app = FastAPI(title=settings.PROJECT_NAME)

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

