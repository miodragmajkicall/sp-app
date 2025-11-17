from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TENANT = {"X-Tenant-Code": "t-demo"}


def test_cash_crud_flow():
    # create
    payload = {
        "entry_date": "2025-11-07",
        "kind": "income",
        "amount": "12.34",
        "note": "pytest e2e",
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
    r = client.patch(
        f"/cash/{cash_id}",
        json={"amount": "99.99", "note": "patched"},
        headers=TENANT,
    )
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


def test_cash_summary_basic():
    """
    Osnovni test za /cash/summary:
    - koristimo poseban tenant 't-summary'
    - upisujemo 3 unosa (2 income, 1 expense)
    - provjeravamo da summary vraća ispravne sume.
    """
    tenant_headers = {"X-Tenant-Code": "t-summary"}

    # 1) Očistimo sve postojeće unose za ovog tenanta,
    #    kako bi test bio idempotentan (radi i kada se baza ne resetuje između run-ova).
    r = client.get("/cash/", headers=tenant_headers)
    assert r.status_code == 200, r.text
    existing_rows = r.json()
    for row in existing_rows:
        rid = row["id"]
        rd = client.delete(f"/cash/{rid}", headers=tenant_headers)
        assert rd.status_code == 204, rd.text

    # 2) kreiramo 3 unosa:
    # income 100.00
    payload1 = {
        "entry_date": "2025-11-01",
        "kind": "income",
        "amount": "100.00",
        "note": "inc-1",
    }
    r = client.post("/cash/", json=payload1, headers=tenant_headers)
    assert r.status_code == 201, r.text

    # expense 40.00
    payload2 = {
        "entry_date": "2025-11-02",
        "kind": "expense",
        "amount": "40.00",
        "note": "exp-1",
    }
    r = client.post("/cash/", json=payload2, headers=tenant_headers)
    assert r.status_code == 201, r.text

    # income 10.00
    payload3 = {
        "entry_date": "2025-11-03",
        "kind": "income",
        "amount": "10.00",
        "note": "inc-2",
    }
    r = client.post("/cash/", json=payload3, headers=tenant_headers)
    assert r.status_code == 201, r.text

    # 3) poziv summary endpointa bez datumske filtracije
    r = client.get("/cash/summary", headers=tenant_headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert set(data.keys()) == {"income", "expense", "net"}

    income = Decimal(str(data["income"]))
    expense = Decimal(str(data["expense"]))
    net = Decimal(str(data["net"]))

    assert income == Decimal("110.00")
    assert expense == Decimal("40.00")
    assert net == Decimal("70.00")
