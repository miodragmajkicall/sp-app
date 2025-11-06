from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .routes import cash as cash_routes

app = FastAPI(title="sp-app API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Integrity error: provjeri polja (npr. kind, amount, tenant_code)."},
    )


app.include_router(cash_routes.router)
