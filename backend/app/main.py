# backend/app/main.py
from fastapi import FastAPI
from .db import ping
from .routes import cash as cash_routes

app = FastAPI(title="sp-app API")

# Rute
app.include_router(cash_routes.router)

# Health
@app.get("/health")
def health():
    try:
        ping()
        return {"status": "ok"}
    except Exception as exc:
        # Nemoj iznositi detalje konekcije u response; dovoljan je 500 sa "error"
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="db error") from exc
