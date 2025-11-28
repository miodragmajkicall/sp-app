import time

import httpx

BASE_URL = "http://localhost:8000"


def _headers_for_tenant(code: str) -> dict:
    return {"X-Tenant-Code": code}


def _create_cash(tenant_code: str, entry_date: str, kind: str, amount: str, suffix: str) -> dict:
    """
    Helper koji kreira jednostavan cash unos za dati tenant.
    Vraća kompletan JSON response (created cash entry).
    """
    headers = _headers_for_tenant(tenant_code)
    payload = {
        "entry_date": entry_date,
        "kind": kind,          # "income" ili "expense"
        "amount": amount,      # npr. "100.00"
        "note": f"Note {suffix}",
    }
    r = httpx.post(f"{BASE_URL}/cash/", json=payload, headers=headers, timeout=5)
    assert r.status_code == 201, r.text
    return r.json()


def test_cash_list_ui_basic_and_pagination():
    """
    Testiramo novi UI endpoint:

    GET /cash/list

    - vraća objekt sa poljima:
        - total (ukupan broj zapisa koji zadovoljavaju filtere)
        - items (lista redova za tabelu u UI-ju)
    - respektuje year/month filtere
    - paginacija preko limit/offset
    """
    tenant_code = f"cash-ui-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    # Kreiramo 3 unosa u dvije različite godine/mjeseca i različitih vrsta
    c1 = _create_cash(tenant_code, "2025-01-10", "income", "100.00", "001-2025-01")
    c2 = _create_cash(tenant_code, "2025-01-15", "expense", "50.00", "002-2025-01")
    c3 = _create_cash(tenant_code, "2026-02-05", "income", "200.00", "003-2026-02")

    created_ids = {c1["id"], c2["id"], c3["id"]}
    assert len(created_ids) == 3

    # --- BEZ FILTERA ---
    r = httpx.get(f"{BASE_URL}/cash/list", headers=headers, timeout=5)
    assert r.status_code == 200, r.text
    data = r.json()

    assert "total" in data
    assert "items" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["items"], list)
    assert data["total"] == 3

    # jedan primjer reda
    row = data["items"][0]
    for key in [
        "id",
        "entry_date",
        "kind",
        "amount",
        "note",
    ]:
        assert key in row

    # --- FILTER: GODINA 2025 ---
    r = httpx.get(
        f"{BASE_URL}/cash/list",
        params={"year": 2025},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    numbers_2025 = {item["id"] for item in data["items"]}
    assert numbers_2025 == {c1["id"], c2["id"]}

    # --- FILTER: GODINA 2026 + MJESEC 2 ---
    r = httpx.get(
        f"{BASE_URL}/cash/list",
        params={"year": 2026, "month": 2},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == c3["id"]

    # --- PAGINACIJA ---
    r1 = httpx.get(
        f"{BASE_URL}/cash/list",
        params={"limit": 1, "offset": 0},
        headers=headers,
        timeout=5,
    )
    r2 = httpx.get(
        f"{BASE_URL}/cash/list",
        params={"limit": 1, "offset": 1},
        headers=headers,
        timeout=5,
    )

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    d1 = r1.json()
    d2 = r2.json()

    assert d1["total"] == 3
    assert d2["total"] == 3
    assert len(d1["items"]) == 1
    assert len(d2["items"]) == 1
    assert d1["items"][0]["id"] != d2["items"][0]["id"]


def test_cash_list_ui_kind_filter():
    """
    Testiramo filter po vrsti unosa (kind = income/expense):

    - kreiramo 3 unosa (2 prihoda, 1 rashod)
    - sa kind=income dobijamo samo prihode
    - sa kind=expense dobijamo samo rashode
    """
    tenant_code = f"cash-ui-kind-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    c1 = _create_cash(tenant_code, "2025-03-01", "income", "100.00", "INC-1")
    c2 = _create_cash(tenant_code, "2025-03-02", "expense", "40.00", "EXP-1")
    c3 = _create_cash(tenant_code, "2025-03-03", "income", "60.00", "INC-2")

    # income samo
    r = httpx.get(
        f"{BASE_URL}/cash/list",
        params={"kind": "income"},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    ids_income = {item["id"] for item in data["items"]}
    assert ids_income == {c1["id"], c3["id"]}
    assert data["total"] == 2

    # expense samo
    r = httpx.get(
        f"{BASE_URL}/cash/list",
        params={"kind": "expense"},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    ids_expense = {item["id"] for item in data["items"]}
    assert ids_expense == {c2["id"]}
    assert data["total"] == 1
