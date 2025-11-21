from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TENANT = {"X-Tenant-Code": "t-demo"}


def _clear_tenant_cash(tenant_code: str) -> None:
    """
    Pomoćna funkcija koja briše sve postojeće cash unose za zadatog tenanta.

    Koristimo je u testovima kako bismo imali čist i ponovljiv (idempotentan)
    kontekst za svaki tenant koji se koristi u testovima.
    """
    headers = {"X-Tenant-Code": tenant_code}
    r = client.get("/cash/", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    for row in rows:
        rid = row["id"]
        rd = client.delete(f"/cash/{rid}", headers=headers)
        assert rd.status_code == 204, rd.text


def test_cash_crud_flow():
    """
    Osnovni e2e flow za jedan tenant:
    - kreiranje unosa
    - dohvat
    - izmjena (PATCH)
    - listanje
    - brisanje
    - provjera da je nakon brisanja 404.
    """
    tenant_code = "t-demo"
    headers = {"X-Tenant-Code": tenant_code}

    # Očistimo prethodne podatke za slučaj ponovnog pokretanja testova
    _clear_tenant_cash(tenant_code)

    # create
    payload = {
        "entry_date": "2025-11-07",
        "kind": "income",
        "amount": "12.34",
        "note": "pytest e2e",
    }
    r = client.post("/cash/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    created = r.json()
    cash_id = created["id"]
    assert isinstance(cash_id, int)

    # get
    r = client.get(f"/cash/{cash_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["note"] == "pytest e2e"

    # patch
    r = client.patch(
        f"/cash/{cash_id}",
        json={"amount": "99.99", "note": "patched"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "99.99"
    assert r.json()["note"] == "patched"

    # list
    r = client.get("/cash/", headers=headers)
    assert r.status_code == 200, r.text
    assert any(row["id"] == cash_id for row in r.json())

    # delete
    r = client.delete(f"/cash/{cash_id}", headers=headers)
    assert r.status_code == 204, r.text

    # get -> 404
    r = client.get(f"/cash/{cash_id}", headers=headers)
    assert r.status_code == 404


def test_cash_summary_basic():
    """
    Osnovni test za /cash/summary:
    - koristimo poseban tenant 't-summary'
    - upisujemo 3 unosa (2 income, 1 expense)
    - provjeravamo da summary vraća ispravne sume.
    """
    tenant_code = "t-summary"
    tenant_headers = {"X-Tenant-Code": tenant_code}

    # 1) Očistimo sve postojeće unose za ovog tenanta,
    #    kako bi test bio idempotentan (radi i kada se baza ne resetuje između run-ova).
    _clear_tenant_cash(tenant_code)

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


def test_cash_list_pagination_and_order():
    """
    Testira da:
    - lista vraća zapise sortirane od najnovijeg ka najstarijem,
    - paginacija (limit/offset) radi očekivano.
    """
    tenant_code = "t-list-page"
    headers = {"X-Tenant-Code": tenant_code}

    _clear_tenant_cash(tenant_code)

    # kreiramo 3 unosa sa različitim datumima
    payloads = [
        {
            "entry_date": "2025-11-01",
            "kind": "income",
            "amount": "10.00",
            "note": "row-1",
        },
        {
            "entry_date": "2025-11-02",
            "kind": "income",
            "amount": "20.00",
            "note": "row-2",
        },
        {
            "entry_date": "2025-11-03",
            "kind": "income",
            "amount": "30.00",
            "note": "row-3",
        },
    ]

    created_ids = []
    for p in payloads:
        r = client.post("/cash/", json=p, headers=headers)
        assert r.status_code == 201, r.text
        created_ids.append(r.json()["id"])

    id1, id2, id3 = created_ids  # redoslijed kreiranja

    # full list
    r = client.get("/cash/", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    returned_ids = [row["id"] for row in rows]

    # očekujemo da je zadnji kreirani prvi u listi (sortirano desc po created_at/id)
    assert returned_ids[:3] == [id3, id2, id1]

    # paginacija: limit=2, offset=0
    r = client.get("/cash/?limit=2&offset=0", headers=headers)
    assert r.status_code == 200, r.text
    rows_page_1 = r.json()
    assert len(rows_page_1) == 2
    assert [row["id"] for row in rows_page_1] == [id3, id2]

    # paginacija: limit=1, offset=1 → drugi element iz pune liste
    r = client.get("/cash/?limit=1&offset=1", headers=headers)
    assert r.status_code == 200, r.text
    rows_page_2 = r.json()
    assert len(rows_page_2) == 1
    assert rows_page_2[0]["id"] == id2


def test_cash_list_date_filters():
    """
    Testira da date_from/date_to filtriranje po entry_date radi ispravno.
    """
    tenant_code = "t-list-date"
    headers = {"X-Tenant-Code": tenant_code}

    _clear_tenant_cash(tenant_code)

    # kreiramo 3 unosa u tri različita dana
    payloads = [
        {
            "entry_date": "2025-11-01",
            "kind": "income",
            "amount": "10.00",
            "note": "d1",
        },
        {
            "entry_date": "2025-11-02",
            "kind": "expense",
            "amount": "20.00",
            "note": "d2",
        },
        {
            "entry_date": "2025-11-03",
            "kind": "income",
            "amount": "30.00",
            "note": "d3",
        },
    ]

    created = []
    for p in payloads:
        r = client.post("/cash/", json=p, headers=headers)
        assert r.status_code == 201, r.text
        created.append(r.json())

    # filtriramo samo '2025-11-02'
    r = client.get(
        "/cash/?date_from=2025-11-02&date_to=2025-11-02",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["entry_date"] == "2025-11-02"
    assert rows[0]["note"] == "d2"

    # filtriramo raspon 2025-11-02..2025-11-03 (2 zapisa)
    r = client.get(
        "/cash/?date_from=2025-11-02&date_to=2025-11-03",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    dates = {row["entry_date"] for row in rows}
    assert dates == {"2025-11-02", "2025-11-03"}


def test_cash_list_tenant_isolation():
    """
    Testira da različiti tenant-i vide samo svoje podatke.
    """
    tenant_a = "t-iso-a"
    tenant_b = "t-iso-b"

    headers_a = {"X-Tenant-Code": tenant_a}
    headers_b = {"X-Tenant-Code": tenant_b}

    _clear_tenant_cash(tenant_a)
    _clear_tenant_cash(tenant_b)

    # tenant A dobija svoj unos
    payload_a = {
        "entry_date": "2025-11-10",
        "kind": "income",
        "amount": "50.00",
        "note": "A-only",
    }
    r = client.post("/cash/", json=payload_a, headers=headers_a)
    assert r.status_code == 201, r.text
    row_a = r.json()
    id_a = row_a["id"]

    # tenant B dobija svoj unos
    payload_b = {
        "entry_date": "2025-11-11",
        "kind": "expense",
        "amount": "30.00",
        "note": "B-only",
    }
    r = client.post("/cash/", json=payload_b, headers=headers_b)
    assert r.status_code == 201, r.text
    row_b = r.json()
    id_b = row_b["id"]

    # list za tenant A → treba da vidi samo svoj unos
    r = client.get("/cash/", headers=headers_a)
    assert r.status_code == 200, r.text
    rows_a = r.json()
    ids_a = {row["id"] for row in rows_a}
    assert id_a in ids_a
    assert id_b not in ids_a

    # list za tenant B → treba da vidi samo svoj unos
    r = client.get("/cash/", headers=headers_b)
    assert r.status_code == 200, r.text
    rows_b = r.json()
    ids_b = {row["id"] for row in rows_b}
    assert id_b in ids_b
    assert id_a not in ids_b
