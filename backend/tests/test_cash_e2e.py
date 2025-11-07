from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TENANT = {"X-Tenant-Code": "t-demo"}

def test_cash_crud_flow():
    # create
    payload = {
        "entry_date": "2025-11-07",
        "kind": "income",
        "amount":  "12.34",
        "note": "pytest e2e"
    }
    r = client.post("/cash/", json=payload, headers=TENANT)
    assert r.status_code == 201, r.text
    created = r.json()
    cash_id = created["id"]
    assert isinstance(cash_id, int)

    # get
    r = client.get(f"/cash/{cash_id}", headers=TENANT)
    assert r.status_code == 200, r.text
    assert r.json()["note"] == "pytest e2e"

    # patch
    r = client.patch(f"/cash/{cash_id}", json={"amount": "99.99", "note": "patched"}, headers=TENANT)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "99.99"
    assert r.json()["note"] == "patched"

    # list
    r = client.get("/cash/", headers=TENANT)
    assert r.status_code == 200, r.text
    assert any(row["id"] == cash_id for row in r.json())

    # delete
    r = client.delete(f"/cash/{cash_id}", headers=TENANT)
    assert r.status_code == 204, r.text

    # get -> 404
    r = client.get(f"/cash/{cash_id}", headers=TENANT)
    assert r.status_code == 404
