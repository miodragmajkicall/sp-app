# /home/miso/dev/sp-app/sp-app/backend/app/main.py
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import (
    health,
    tenants,
    cash,
    invoices,
    input_invoices,
    invoice_attachments,
    tax,
    dashboard,
    sam,
)
from app.models import FinalizedPeriodModificationError

# Tagovi za OpenAPI dokumentaciju – čisto da bude preglednije u Swagger-u
tags_metadata = [
    {
        "name": "health",
        "description": "Osnovni health check endpointi (API & baza).",
    },
    {
        "name": "tenants",
        "description": "Upravljanje tenantima (logički kupci / firme).",
    },
    {
        "name": "cash",
        "description": "Keš knjiga – prihodi i rashodi po tenantima.",
    },
    {
        "name": "invoices",
        "description": "Izlazne fakture koje SP izdaje svojim klijentima.",
    },
    {
        "name": "input-invoices",
        "description": "Ulazne fakture (računi dobavljača) koje SP prima.",
    },
    {
        "name": "invoice-attachments",
        "description": "Upload i download PDF priloga uz izlazne fakture.",
    },
    {
        "name": "tax",
        "description": "Mjesečni i godišnji obračuni poreza i doprinosa.",
    },
    {
        "name": "dashboard",
        "description": "Kratki sažeci za početni ekran / dashboard.",
    },
    {
        "name": "sam",
        "description": "SAM blok – pregled prihoda, rashoda i obaveza.",
    },
    {
        "name": "meta",
        "description": "Meta informacije o API-ju (verzija, opis, moduli).",
    },
]

app = FastAPI(
    title="SP-APP API",
    description=(
        "Backend API za SP-APP – aplikaciju za samostalne preduzetnike "
        "u BiH/RS (keš knjiga, fakture, porezi, izvještaji, dashboard...)."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
)

# ======================================================
#  CORS (za frontend/web & mobilne klijente)
# ======================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # kasnije možemo suziti na konkretne domene
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
#  GLOBALNI HANDLER ZA FINALIZOVANE PERIODЕ
# ======================================================


@app.exception_handler(FinalizedPeriodModificationError)
async def finalized_period_exception_handler(
    request: Request,
    exc: FinalizedPeriodModificationError,
):
    """
    Globalni handler za slučajeve kada pokušamo mijenjati podatke
    (fakture, cash unose...) u poreskom periodu koji je već finalizovan
    preko TAX modula.

    Važno za testove:
    - vraća HTTP 400
    - `detail` je tačno `str(exc)`, npr.
      "Cannot modify data for finalized tax period 2025-03 for tenant lock-inv-1234."
    """
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


# ======================================================
#  GLOBALNI /meta ENDPOINT
# ======================================================


@app.get(
    "/meta",
    tags=["meta"],
    summary="Osnovne informacije o API-ju",
    description=(
        "Vraća kratke meta informacije o API-ju – naziv, verziju i opis.\n\n"
        "Ovo je korisno za health/dashboard widgete, monitoring ili "
        "brzu provjeru koja verzija backend-a je trenutno deploy-ovana."
    ),
)
def get_meta() -> dict:
    """
    Jednostavan endpoint za meta informacije o API-ju.
    """
    return {
        "app": "sp-app-api",
        "version": app.version,
        "title": app.title,
        "description": app.description,
    }


# ======================================================
#  REGISTRACIJA SVIH ROUTERA
# ======================================================

# Health & status
app.include_router(health.router)

# Tenanti
app.include_router(tenants.router)

# Keš knjiga (cash)
app.include_router(cash.router)

# Izlazne fakture
app.include_router(invoices.router)

# Ulazne fakture (dobavljači)
app.include_router(input_invoices.router)

# Prilozi (PDF) uz fakture
app.include_router(invoice_attachments.router)

# Porezi i doprinosi (mjesečni/godišnji obračuni)
app.include_router(tax.router)

# Dashboard pregledi
app.include_router(dashboard.router)

# SAM blok (sumarni financijski pregled)
app.include_router(sam.router)
