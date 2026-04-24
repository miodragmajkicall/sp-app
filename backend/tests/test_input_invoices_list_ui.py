from __future__ import annotations
import pytest

pytestmark = pytest.mark.live_api

import time
from typing import Dict, Any

import httpx

BASE_URL = "http://localhost:8000"


def _headers_for_tenant(code: str) -> Dict[str, str]:
    return {"X-Tenant-Code": code}


def _create_input_invoice(
    tenant_code: str,
    suffix: str,
    issue_date: str,
    supplier_name: str,
) -> Dict[str, Any]:
    """
    Helper koji kreira jednu ulaznu fakturu za zadati tenant preko HTTP API-ja.
    Vraća kompletan JSON response (kreirana faktura).
    """
    headers = _headers_for_tenant(tenant_code)
    payload = {
        "supplier_name": supplier_name,
        "supplier_tax_id": f"TAX-{suffix}",
        "supplier_address": f"Adresa {suffix}",
        "invoice_number": f"UI-{suffix}",
        "issue_date": issue_date,
        "due_date": issue_date,
        "total_base": "100.00",
        "total_vat": "17.00",
        "total_amount": "117.00",
        "currency": "BAM",
        "note": f"Napomena {suffix}",
    }

    r = httpx.post(
        f"{BASE_URL}/input-invoices",
        json=payload,
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 201, r.text
    return r.json()


# ======================================================
#  BASIC + PAGINACIJA + YEAR/MONTH FILTER
# ======================================================


def test_input_invoices_list_ui_basic_and_pagination():
    """
    Testiramo novi UI endpoint:

    GET /input-invoices/list

    - vraća objekt sa poljima:
        - total (ukupan broj faktura koje zadovoljavaju filtere)
        - items (lista redova za tabelu u UI-ju)
    - respektuje year/month filtere
    - paginacija preko limit/offset
    """
    tenant_code = f"input-ui-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    # Kreiramo 3 ulazne fakture u dvije različite godine/mjeseca
    inv_1 = _create_input_invoice(
        tenant_code,
        suffix="001-2025-01",
        issue_date="2025-01-10",
        supplier_name="Elektro A",
    )
    inv_2 = _create_input_invoice(
        tenant_code,
        suffix="002-2025-01",
        issue_date="2025-01-20",
        supplier_name="Elektro B",
    )
    inv_3 = _create_input_invoice(
        tenant_code,
        suffix="003-2026-02",
        issue_date="2026-02-05",
        supplier_name="Drugi Dobavljač",
    )

    created_ids = {inv_1["id"], inv_2["id"], inv_3["id"]}
    assert len(created_ids) == 3

    # --- BEZ FILTERA ---
    r = httpx.get(
        f"{BASE_URL}/input-invoices/list",
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert "total" in data
    assert "items" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["items"], list)
    assert data["total"] == 3
    assert len(data["items"]) == 3

    row = data["items"][0]
    # Provjera da UI red ima osnovna polja koja očekujemo
    for key in [
        "id",
        "tenant_code",
        "supplier_name",
        "invoice_number",
        "issue_date",
        "due_date",
        "total_base",
        "total_vat",
        "total_amount",
        "currency",
        "created_at",
    ]:
        assert key in row

    # --- YEAR/MONTH FILTER ---
    # 2025-01 -> treba da vrati inv_1 i inv_2
    r = httpx.get(
        f"{BASE_URL}/input-invoices/list",
        params={"year": 2025, "month": 1},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data_2025_01 = r.json()
    assert data_2025_01["total"] == 2
    numbers = sorted(item["invoice_number"] for item in data_2025_01["items"])
    assert numbers == ["UI-001-2025-01", "UI-002-2025-01"]

    # --- PAGINACIJA ---
    r1 = httpx.get(
        f"{BASE_URL}/input-invoices/list",
        params={"limit": 1, "offset": 0},
        headers=headers,
        timeout=5,
    )
    r2 = httpx.get(
        f"{BASE_URL}/input-invoices/list",
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


# ======================================================
#  SUPPLIER_NAME FILTER
# ======================================================


def test_input_invoices_list_ui_supplier_name_filter():
    """
    Testiramo filter po nazivu dobavljača (supplier_name):

    - kreiramo 3 fakture (2 sa 'Elektro...', 1 sa 'Vodovod')
    - sa supplier_name='Elektro' dobijamo samo prve dvije
    """
    tenant_code = f"input-ui-supp-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    inv_1 = _create_input_invoice(
        tenant_code,
        suffix="ELE-1",
        issue_date="2025-03-01",
        supplier_name="Elektrodistribucija A",
    )
    inv_2 = _create_input_invoice(
        tenant_code,
        suffix="ELE-2",
        issue_date="2025-03-05",
        supplier_name="Elektro Servis B",
    )
    _create_input_invoice(
        tenant_code,
        suffix="VOD-1",
        issue_date="2025-03-10",
        supplier_name="Vodovod A",
    )

    r = httpx.get(
        f"{BASE_URL}/input-invoices/list",
        params={"supplier_name": "Elektro"},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert "total" in data
    assert "items" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2

    for row in data["items"]:
        assert row["supplier_name"].startswith("Elektro")
        assert row["tenant_code"] == tenant_code
