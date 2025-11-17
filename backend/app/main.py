from fastapi import FastAPI

from .routes import health as health_routes
from .routes import tenants as tenants_routes
from .routes import debug as debug_routes
from .routes import cash as cash_routes

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
        "- vođenje evidencije prihoda i rashoda po tenantu (cashbook modul)\n"
        "- health-check endpointi za potrebe monitoringa i CI/CD\n\n"
        "Dokumentacija je organizovana po tagovima: **health**, **tenants**, **cash** i **debug**."
    ),
    openapi_tags=tags_metadata,
)

# redoslijed nije kritičan, ali health prvo radi brzog pinga
app.include_router(health_routes.router)
app.include_router(tenants_routes.router)
app.include_router(debug_routes.router)
app.include_router(cash_routes.router)
