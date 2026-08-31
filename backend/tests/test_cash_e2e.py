# /home/miso/dev/sp-app/sp-app/backend/tests/test_cash_e2e.py
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Poseban tenant za e2e cash testove – NE koristimo 't-demo'
TEST_TENANT_CASH_E2E = "cash-e2e-demo"


def _clear_tenant_cash(tenant_code: str) -> None:
    """
    Pomoćna funkcija koja briše sve postojeće cash unose za zadatog tenanta.

    Koristimo je u testovima kako bismo imali čist i ponovljiv (idempotentan)
    kontekst za svaki tenant koji se koristi u testovima.

    VAŽNO: u e2e testovima koristimo poseban tenant (npr. 'cash-e2e-demo'),
    kako ne bismo dirali razvojne podatke za 't-demo' koje unosiš kroz UI.
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
    # Koristimo poseban test tenant, da ne diramo 't-demo'
    tenant_code = TEST_TENANT_CASH_E2E
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
    Testira /cash/summary:
    - ukupni income / expense / net,
    - neto tok posebno za kasu i banku,
    - broj zapisa,
    - datumski filter,
    - zaštitu od obrnutog datumskog raspona.
    """
    tenant_code = "t-summary"
    tenant_headers = {"X-Tenant-Code": tenant_code}

    _clear_tenant_cash(tenant_code)

    payload1 = {
        "entry_date": "2025-11-01",
        "kind": "income",
        "amount": "100.00",
        "account": "cash",
        "note": "inc-cash",
    }
    r = client.post("/cash/", json=payload1, headers=tenant_headers)
    assert r.status_code == 201, r.text

    payload2 = {
        "entry_date": "2025-11-02",
        "kind": "expense",
        "amount": "40.00",
        "account": "cash",
        "note": "exp-cash",
    }
    r = client.post("/cash/", json=payload2, headers=tenant_headers)
    assert r.status_code == 201, r.text

    payload3 = {
        "entry_date": "2025-11-03",
        "kind": "income",
        "amount": "10.00",
        "account": "bank",
        "note": "inc-bank",
    }
    r = client.post("/cash/", json=payload3, headers=tenant_headers)
    assert r.status_code == 201, r.text

    r = client.get("/cash/summary", headers=tenant_headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert set(data.keys()) == {
        "income",
        "expense",
        "net",
        "cash_net",
        "bank_net",
        "total_count",
    }

    assert Decimal(str(data["income"])) == Decimal("110.00")
    assert Decimal(str(data["expense"])) == Decimal("40.00")
    assert Decimal(str(data["net"])) == Decimal("70.00")
    assert Decimal(str(data["cash_net"])) == Decimal("60.00")
    assert Decimal(str(data["bank_net"])) == Decimal("10.00")
    assert data["total_count"] == 3

    r = client.get(
        "/cash/summary",
        params={
            "date_from": "2025-11-02",
            "date_to": "2025-11-03",
        },
        headers=tenant_headers,
    )
    assert r.status_code == 200, r.text
    filtered = r.json()

    assert Decimal(str(filtered["income"])) == Decimal("10.00")
    assert Decimal(str(filtered["expense"])) == Decimal("40.00")
    assert Decimal(str(filtered["net"])) == Decimal("-30.00")
    assert Decimal(str(filtered["cash_net"])) == Decimal("-40.00")
    assert Decimal(str(filtered["bank_net"])) == Decimal("10.00")
    assert filtered["total_count"] == 2

    r = client.get(
        "/cash/summary",
        params={
            "date_from": "2025-11-03",
            "date_to": "2025-11-01",
        },
        headers=tenant_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == (
        "date_from must be less than or equal to date_to"
    )


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


def test_cash_patch_null_contract():
    """
    PATCH contract:
    - obavezna DB polja ne smiju biti eksplicitno null;
    - note smije biti null i time se postojeća napomena briše.
    """
    tenant_code = "t-cash-patch-null"
    headers = {"X-Tenant-Code": tenant_code}

    _clear_tenant_cash(tenant_code)

    r = client.post(
        "/cash/",
        json={
            "entry_date": "2025-11-17",
            "kind": "income",
            "amount": "75.00",
            "account": "bank",
            "note": "note to clear",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    cash_id = r.json()["id"]

    for field_name in ("entry_date", "kind", "amount", "account"):
        r = client.patch(
            f"/cash/{cash_id}",
            json={field_name: None},
            headers=headers,
        )

        assert r.status_code == 422, (
            f"{field_name} unexpectedly accepted null: {r.text}"
        )

    r = client.patch(
        f"/cash/{cash_id}",
        json={"note": None},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    assert r.json()["note"] is None

def test_cash_list_canonical_contract_and_filters():
    tenant_code = "t-cash-canonical-list"
    headers = {"X-Tenant-Code": tenant_code}

    _clear_tenant_cash(tenant_code)

    payloads = [
        {
            "entry_date": "2025-11-01",
            "kind": "income",
            "amount": "100.00",
            "account": "cash",
            "note": "cash-income",
        },
        {
            "entry_date": "2025-11-02",
            "kind": "expense",
            "amount": "40.00",
            "account": "bank",
            "note": "bank-expense",
        },
        {
            "entry_date": "2025-11-03",
            "kind": "income",
            "amount": "60.00",
            "account": "bank",
            "note": "bank-income",
        },
    ]

    created = []
    for payload in payloads:
        r = client.post("/cash/", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        created.append(r.json())

    r = client.get(
        "/cash/list",
        params={"limit": 2, "offset": 0},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) == 2

    assert [row["id"] for row in data["items"]] == [
        created[2]["id"],
        created[1]["id"],
    ]

    manual = data["items"][0]
    assert manual["source_type"] == "manual"
    assert manual["source_document_id"] is None
    assert manual["source_document_number"] is None
    assert manual["source_party_name"] is None

    r = client.get(
        "/cash/list",
        params={
            "date_from": "2025-11-02",
            "date_to": "2025-11-03",
            "account": "bank",
            "kind": "income",
            "source_type": "manual",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == created[2]["id"]


def test_cash_list_canonical_validation():
    headers = {"X-Tenant-Code": "t-cash-list-validation"}

    invalid_queries = [
        {"kind": "invalid"},
        {"account": "invalid"},
        {"source_type": "invalid"},
        {"month": 11},
        {
            "date_from": "2025-11-30",
            "date_to": "2025-11-01",
        },
    ]

    for params in invalid_queries:
        r = client.get(
            "/cash/list",
            params=params,
            headers=headers,
        )

        assert r.status_code == 422, (
            f"Query unexpectedly accepted: {params!r}: {r.text}"
        )



def test_manual_cash_recognition_class_contract():
    tenant_code = "t-cash-recognition-class"
    headers = {"X-Tenant-Code": tenant_code}

    _clear_tenant_cash(tenant_code)

    default_response = client.post(
        "/cash/",
        json={
            "entry_date": "2025-11-20",
            "kind": "income",
            "amount": "100.00",
            "account": "cash",
            "note": "default classification",
        },
        headers=headers,
    )
    assert default_response.status_code == 201, default_response.text
    default_row = default_response.json()
    assert default_row["recognition_class"] == "business_activity"

    cash_only_response = client.post(
        "/cash/",
        json={
            "entry_date": "2025-11-21",
            "kind": "expense",
            "amount": "25.00",
            "account": "bank",
            "recognition_class": "cash_only",
            "note": "cash only",
        },
        headers=headers,
    )
    assert cash_only_response.status_code == 201, cash_only_response.text
    cash_only_row = cash_only_response.json()
    assert cash_only_row["recognition_class"] == "cash_only"

    cash_id = cash_only_row["id"]

    patch_response = client.patch(
        f"/cash/{cash_id}",
        json={"recognition_class": "business_activity"},
        headers=headers,
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["recognition_class"] == "business_activity"

    null_response = client.patch(
        f"/cash/{cash_id}",
        json={"recognition_class": None},
        headers=headers,
    )
    assert null_response.status_code == 422, null_response.text

    invalid_create = client.post(
        "/cash/",
        json={
            "entry_date": "2025-11-22",
            "kind": "income",
            "amount": "10.00",
            "account": "cash",
            "recognition_class": "invalid",
        },
        headers=headers,
    )
    assert invalid_create.status_code == 422, invalid_create.text

    list_response = client.get(
        "/cash/list",
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text

    listed_by_id = {
        row["id"]: row
        for row in list_response.json()["items"]
    }
    assert listed_by_id[default_row["id"]]["recognition_class"] == "business_activity"
    assert listed_by_id[cash_id]["recognition_class"] == "business_activity"
