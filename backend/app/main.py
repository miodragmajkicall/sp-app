from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .routes import health as health_routes
from .routes import tenants as tenants_routes
from .routes import debug as debug_routes
from .routes import cash as cash_routes
from .routes import invoices as invoices_routes
from .routes import tax as tax_routes
from .models import FinalizedPeriodModificationError
from .schemas.tax import ErrorResponse

tags_metadata = [
    {
        "name": "health",
        "description": "Osnovni health-check endpointi za provjeru rada API-ja i baze podataka.",
    },
    {
        "name": "tenants",
        "description": (
            "Upravljanje tenantima (klijentima) aplikacije. "
            "Tenant predstavlja jednog krajnjeg korisnika (npr. jednog samostalnog preduzetnika) "
            "sa svojim jedinstvenim code-om i imenom."
        ),
    },
    {
        "name": "cash",
        "description": (
            "Evidencija gotovinskih tokova (prihodi i rashodi) po tenantu. "
            "Obuhvata unos, ažuriranje, brisanje i pregled cash unosa, kao i sumarne preglede "
            "ukupnih prihoda, rashoda i neto rezultata po periodu."
        ),
    },
    {
        "name": "invoices",
        "description": (
            "Fakture po tenantu – kreiranje, pregled i brisanje faktura sa stavkama, "
            "uključujući izračun osnovice, PDV-a i ukupnog iznosa po fakturi. "
            "Predviđeno za jednostavno izdavanje računa krajnjim klijentima."
        ),
    },
    {
        "name": "tax",
        "description": (
            "Modul za **mjesečni i godišnji porezni obračun po tenantu** zasnovan na podacima iz "
            "cash i invoices modula.\n\n"
            "Funkcionalnosti obuhvataju:\n"
            "- DUMMY izračun poreza i doprinosa po mjesecu (preview i auto obračun),\n"
            "- finalizaciju mjesečnog obračuna i trajno čuvanje rezultata,\n"
            "- istoriju finalizovanih mjeseci i status (koji mjeseci su zaključani),\n"
            "- godišnji porezni obračun (preview) na osnovu finalizovanih mjeseci,\n"
            "- finalizaciju godišnjeg obračuna i zaključavanje godine.\n\n"
            "Modul takođe uvodi **business lock**: nakon finalizacije određenog perioda "
            "(mjeseca/godine), onemogućene su izmjene podataka koji utiču na taj period "
            "i vraća se jasna greška aplikativnog nivoa.\n\n"
            "**Napomena:** Poreski algoritam je trenutno pojednostavljen (DUMMY) i služi za "
            "razvoj i testiranje – nije pravni savjet niti tačan model poreskog sistema."
        ),
    },
    {
        "name": "debug",
        "description": (
            "Interni i pomoćni endpointi za razvoj i debug. "
            "Ovi endpointi nisu namijenjeni krajnjim korisnicima u produkciji."
        ),
    },
]

app = FastAPI(
    title="sp-app API",
    version="0.1.0",
    description=(
        "Backend API za *sp-app* – aplikaciju namijenjenu malim biznisima i "
        "samostalnim preduzetnicima (SP).\n\n"
        "API pokriva:\n"
        "- registraciju i upravljanje tenantima (klijentima aplikacije),\n"
        "- vođenje evidencije prihoda i rashoda po tenantu (cashbook modul),\n"
        "- izdavanje faktura sa stavkama i PDV obračunom (invoices modul),\n"
        "- DUMMY porezni modul za razvoj i simulaciju **mjesečnih i godišnjih obračuna** "
        "sa zaključavanjem perioda (tax modul),\n"
        "- health-check endpointi za potrebe monitoringa i CI/CD.\n\n"
        "Dokumentacija je organizovana po tagovima: **health**, **tenants**, **cash**, "
        "**invoices**, **tax** i **debug**.\n\n"
        "Ovaj API je backend osnova za web i mobilne klijente sp-app platforme."
    ),
    openapi_tags=tags_metadata,
)


@app.exception_handler(FinalizedPeriodModificationError)
async def finalized_period_modification_handler(
    request: Request, exc: FinalizedPeriodModificationError
) -> JSONResponse:
    """
    Globalni handler koji business-lock grešku pretvara u jasan 400 odgovor,
    kako bi klijentske aplikacije (web/mobilne) mogle jednostavno da reaguju.
    """
    payload = ErrorResponse(
        detail=(
            f"Cannot modify data for finalized tax period "
            f"{exc.year:04d}-{exc.month:02d}."
        )
    )
    return JSONResponse(
        status_code=400,
        content=payload.model_dump(),
    )


# redoslijed nije kritičan, ali health prvo radi brzog pinga
app.include_router(health_routes.router)
app.include_router(tenants_routes.router)
app.include_router(debug_routes.router)
app.include_router(cash_routes.router)
app.include_router(invoices_routes.router)
app.include_router(tax_routes.router)
