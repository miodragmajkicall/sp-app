import time

import httpx

BASE_URL = "http://localhost:8000"


def _headers_for_tenant(code: str) -> dict:
    return {"X-Tenant-Code": code}


def _create_invoice(tenant_code: str, suffix: str, issue_date: str) -> dict:
    """
    Helper koji kreira jednostavnu fakturu za dati tenant.
    Vraća kompletan JSON response (created invoice).
    """
    headers = _headers_for_tenant(tenant_code)
    payload = {
        "invoice_number": f"UI-{suffix}",
        "issue_date": issue_date,
        "due_date": issue_date,
        "buyer_name": f"UI Buyer {suffix}",
        "buyer_address": f"Adresa {suffix}",
        "items": [
            {
                "description": f"Usluga {suffix}",
                "quantity": "1.00",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
    }
    r = httpx.post(f"{BASE_URL}/invoices/", json=payload, headers=headers, timeout=5)
    assert r.status_code == 201, r.text
    return r.json()


def test_invoices_list_ui_basic_and_pagination():
    """
    Testiramo novi UI endpoint:

    GET /invoices/list

    - vraća objekt sa poljima:
        - total (ukupan broj faktura koje zadovoljavaju filtere)
        - items (lista redova za tabelu u UI-ju)
    - respektuje year/month filtere
    - paginacija preko limit/offset
    """
    tenant_code = f"inv-ui-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    # Kreiramo 3 fakture u dvije različite godine/mjeseca
    inv_1 = _create_invoice(tenant_code, "001-2025-01", "2025-01-10")
    inv_2 = _create_invoice(tenant_code, "002-2025-02", "2025-02-15")
    inv_3 = _create_invoice(tenant_code, "003-2026-01", "2026-01-05")

    created_ids = {inv_1["id"], inv_2["id"], inv_3["id"]}
    assert len(created_ids) == 3

    # --- BEZ FILTERA ---
    r = httpx.get(f"{BASE_URL}/invoices/list", headers=headers, timeout=5)
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
        "invoice_number",
        "issue_date",
        "due_date",
        "buyer_name",
        "buyer_address",
        "total_base",
        "total_vat",
        "total_amount",
    ]:
        assert key in row

    # opcioni flag is_paid (za status plaćanja)
    assert "is_paid" in row
    # nove fakture po defaultu treba da budu neplaćene
    assert row["is_paid"] is False

    # --- FILTER: GODINA ---
    r = httpx.get(
        f"{BASE_URL}/invoices/list",
        params={"year": 2025},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200
    d_2025 = r.json()
    assert d_2025["total"] == 2

    # --- FILTER: GODINA + MJESEC ---
    r = httpx.get(
        f"{BASE_URL}/invoices/list",
        params={"year": 2025, "month": 2},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200
    d_2025_02 = r.json()
    assert d_2025_02["total"] == 1


def test_invoices_list_ui_unpaid_only_filter():
    """
    Testiramo filter za neplaćene fakture:

    - kreiramo 3 fakture
    - jednu označimo kao plaćenu
    - sa unpaid_only=true dobijamo samo neplaćene fakture
    """
    tenant_code = f"inv-ui-unpaid-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    inv_1 = _create_invoice(tenant_code, "001", "2025-01-10")
    inv_2 = _create_invoice(tenant_code, "002", "2025-01-15")
    inv_3 = _create_invoice(tenant_code, "003", "2025-01-20")

    # označimo jednu fakturu kao plaćenu preko dedicated endpoint-a
    r = httpx.post(
        f"{BASE_URL}/invoices/{inv_2['id']}/mark-paid",
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["id"] == inv_2["id"]
    assert updated["is_paid"] is True

    # --- UNPAID ONLY ---
    r = httpx.get(
        f"{BASE_URL}/invoices/list",
        params={"unpaid_only": "true"},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert "total" in data and "items" in data
    # očekujemo da je broj neplaćenih 2
    assert data["total"] == 2
    ids = {row["id"] for row in data["items"]}
    assert inv_2["id"] not in ids
    assert inv_1["id"] in ids
    assert inv_3["id"] in ids

    # sanity check: bez unpaid_only -> sve 3
    r_all = httpx.get(
        f"{BASE_URL}/invoices/list",
        headers=headers,
        timeout=5,
    )
    assert r_all.status_code == 200
    d_all = r_all.json()
    assert d_all["total"] == 3
