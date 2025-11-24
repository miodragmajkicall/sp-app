from fastapi import FastAPI

from .routes import health as health_routes
from .routes import tenants as tenants_routes
from .routes import debug as debug_routes
from .routes import cash as cash_routes
from .routes import invoices as invoices_routes
from .routes import tax as tax_routes

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
            "uključujući izračun osnovice, PDV-a i ukupnog iznosa."
        ),
    },
    {
        "name": "tax",
        "description": (
            "DUMMY modul za mjesečni porezni obračun po tenantu.\n\n"
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
        "- izdavanje faktura sa stavkama i PDV obračunom (invoices modul)\n"
        "- DUMMY porezni modul za razvoj i simulaciju mjesečnih obračuna (tax modul)\n"
        "- health-check endpointi za potrebe monitoringa i CI/CD\n\n"
        "Dokumentacija je organizovana po tagovima: **health**, **tenants**, **cash**, "
        "**invoices**, **tax** i **debug**."
    ),
    openapi_tags=tags_metadata,
)

# redoslijed nije kritičan, ali health prvo radi brzog pinga
app.include_router(health_routes.router)
app.include_router(tenants_routes.router)
app.include_router(debug_routes.router)
app.include_router(cash_routes.router)
app.include_router(invoices_routes.router)
app.include_router(tax_routes.router)
