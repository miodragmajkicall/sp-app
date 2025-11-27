from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .routes import health as health_routes
from .routes import tenants as tenants_routes
from .routes import debug as debug_routes
from .routes import cash as cash_routes
from .routes import invoices as invoices_routes
from .routes import invoice_attachments as invoice_attachments_routes
from .routes import tax as tax_routes
from .routes import sam as sam_routes
from .routes import dashboard as dashboard_routes
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
            "Tenant predstavlja jednog krajnjeg korisnika (npr. jednog SP-a) sa svojim code-om i imenom."
        ),
    },
    {
        "name": "cash",
        "description": (
            "Evidencija gotovinskih tokova (prihodi i rashodi) po tenantu. "
            "Obuhvata unos, ažuriranje, brisanje i pregled cash unosa, kao i sumarne preglede."
        ),
    },
    {
        "name": "invoices",
        "description": (
            "Fakture po tenantu – kreiranje, pregled i brisanje faktura sa stavkama, "
            "uključujući izračun osnovice, PDV-a i ukupnog iznosa.\n\n"
            "U ovaj domen spadaju i **attachment-i ulaznih faktura** koji se uploaduju "
            "radi kasnije OCR obrade i automatskog unosa ulaznih računa."
        ),
    },
    {
        "name": "tax",
        "description": (
            "DUMMY modul za mjesečni i godišnji porezni obračun po tenantu.\n\n"
            "Ovaj modul koristi pojednostavljene (dummy) porezne stope i služi za razvoj i testiranje:\n"
            "- sumarizacija mjesečnih prihoda i rashoda,\n"
            "- izračun oporezive osnovice,\n"
            "- izračun poreza i doprinosa,\n"
            "- prikaz ukupne obaveze za uplatu.\n\n"
            "**Napomena:** Ovo nije pravni savjet niti tačan model poreskog sistema, "
            "već razvojni alat u okviru sp-app API-ja."
        ),
    },
    {
        "name": "sam",
        "description": (
            "SAM (samostalni preduzetnik) pregled obaveza prema državi.\n\n"
            "Ovaj modul koristi podatke iz poreskog modula (tax) kako bi SP-u dao jasan pregled:\n"
            "- koliko mjesečno duguje državi (porez + doprinosi),\n"
            "- koja je ukupna godišnja obaveza,\n"
            "- koji mjeseci su već zaključani.\n\n"
            "Služi kao osnova za SAM dashboard i planiranje uplata."
        ),
    },
    {
        "name": "dashboard",
        "description": (
            "Kombinovani pregled ključnih brojki za jednog tenanta (cash, fakture, tax) "
            "za zadatu godinu. Koristi se za početni ekran u UI-ju."
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
        "Backend API za *sp-app* – aplikaciju namijenjenu malim biznisima i samostalnim preduzetnicima.\n\n"
        "API pokriva:\n"
        "- registraciju i upravljanje tenantima (klijentima aplikacije)\n"
        "- vođenje evidencije prihoda i rashoda po tenantu (cash modul)\n"
        "- izdavanje faktura sa stavkama i PDV obračunom (invoices modul)\n"
        "- upload attachment-a ulaznih faktura radi kasnije OCR obrade (invoice-attachments)\n"
        "- DUMMY porezni modul za razvoj i simulaciju mjesečnih/godišnjih obračuna (tax modul)\n"
        "- SAM pregled obaveza prema državi za jednog SP-a (sam modul)\n"
        "- dashboard sa ključnim brojkama po godini (dashboard modul)\n"
        "- health-check endpointi za potrebe monitoringa i CI/CD\n\n"
        "Dokumentacija je organizovana po tagovima: **health**, **tenants**, **cash**, "
        "**invoices**, **tax**, **sam**, **dashboard** i **debug**."
    ),
    openapi_tags=tags_metadata,
)


@app.exception_handler(FinalizedPeriodModificationError)
async def finalized_period_modification_handler(
    request: Request, exc: FinalizedPeriodModificationError
) -> JSONResponse:
    """
    Globalni handler koji business lock grešku pretvara u jasan 400 odgovor.
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
app.include_router(invoice_attachments_routes.router)
app.include_router(tax_routes.router)
app.include_router(sam_routes.router)
app.include_router(dashboard_routes.router)
