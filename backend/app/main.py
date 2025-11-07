from fastapi import FastAPI
from .routes import health as health_routes
from .routes import tenants as tenants_routes
from .routes import debug as debug_routes
from .routes import cash as cash_routes

app = FastAPI(title="sp-app API", version="0.1.0")

# redoslijed nije kritičan, ali health prvo radi brzog pinga
app.include_router(health_routes.router)
app.include_router(tenants_routes.router)
app.include_router(debug_routes.router)
app.include_router(cash_routes.router)
