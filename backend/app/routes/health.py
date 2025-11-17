from fastapi import APIRouter

from app.db import db_ping

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Osnovni health-check API-ja",
    description=(
        "Jednostavan endpoint koji služi za provjeru da li je aplikacija podignuta.\n\n"
        "Vraća JSON objekt `{ \"status\": \"ok\" }` ukoliko je API dostupan."
    ),
)
def health():
    return {"status": "ok"}


@router.get(
    "/db/health",
    summary="Health-check baze podataka",
    description=(
        "Provjerava dostupnost baze podataka jednostavnim ping pozivom.\n\n"
        "Ako je baza dostupna, vraća JSON objekt `{ \"db\": \"ok\" }`. "
        "U suprotnom će biti podignut exception na nivou konekcije."
    ),
)
def db_health():
    # samo ping; test očekuje baš {"db": "ok"}
    db_ping()
    return {"db": "ok"}
