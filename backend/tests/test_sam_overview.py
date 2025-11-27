from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sam_overview_path_registered_in_openapi() -> None:
    """
    Minimalni smoke-test za SAM yearly overview domen.

    Cilj ovog testa nije detaljna provjera poslovne logike,
    nego potvrda da je SAM router pravilno registrovan u aplikaciji
    i da se pojavljuje u OpenAPI šemi.

    Na ovaj način:
    - izbjegavamo direktno petljanje sa DB konekcijama u ovom test fajlu
    - i dalje imamo pokrivenost da /sam endpoint postoji u API-ju
    """
    resp = client.get("/openapi.json")
    assert resp.status_code == 200

    data = resp.json()
    paths = data.get("paths", {})

    # Očekujemo da postoji bar jedan path koji počinje sa "/sam"
    sam_paths = [p for p in paths.keys() if p.startswith("/sam")]
    assert sam_paths, "Očekuje se bar jedan SAM endpoint u OpenAPI paths"
