import pytest
import time

pytestmark = pytest.mark.live_api

import httpx

BASE_URL = "http://localhost:8000"


def _headers_for_tenant(code: str) -> dict:
    return {"X-Tenant-Code": code}


def _finalize_month(tenant_code: str, year: int, month: int) -> None:
    """
    Pomoćni helper koji poziva POST /tax/monthly/finalize
    za dati tenant/year/month i očekuje uspješan 200 odgovor.
    """
    headers = _headers_for_tenant(tenant_code)
    r = httpx.post(
        f"{BASE_URL}/tax/monthly/finalize",
        params={"year": year, "month": month},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text


def test_cannot_delete_invoice_in_finalized_month():
    """
    Scenario:
    - kreiramo fakturu za određeni mjesec (npr. 2025-03)
    - finalizujemo taj mjesec preko /tax/monthly/finalize
    - pokušamo obrisati fakturu
    -> očekujemo 400 + poruku da je period finalizovan
    """
    tenant_code = f"lock-inv-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    payload = {
        "invoice_number": "LOCK-001",
        "issue_date": "2025-03-10",
        "due_date": "2025-03-20",
        "buyer_name": "Lock Buyer d.o.o.",
        "buyer_address": "Banja Luka",
        "items": [
            {
                "description": "Usluga X",
                "quantity": "1.00",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
    }

    # --- CREATE invoice ---
    r = httpx.post(
        f"{BASE_URL}/invoices/", json=payload, headers=headers, timeout=5
    )
    assert r.status_code == 201, r.text
    created = r.json()
    invoice_id = created["id"]
    assert isinstance(invoice_id, int)

    # --- FINALIZE mjeseca 2025-03 za ovog tenanta ---
    _finalize_month(tenant_code=tenant_code, year=2025, month=3)

    # --- DELETE nakon finalizacije -> treba da bude blokirano ---
    r = httpx.delete(
        f"{BASE_URL}/invoices/{invoice_id}", headers=headers, timeout=5
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert "detail" in body
    # Poruka dolazi iz globalnog handlera u main.py
    assert "Cannot modify data for finalized tax period 2025-03" in body["detail"]


def test_cannot_delete_cash_entry_in_finalized_month():
    """
    Scenario:
    - kreiramo cash entry za određeni mjesec (npr. 2025-04)
    - finalizujemo taj mjesec preko /tax/monthly/finalize
    - pokušamo obrisati cash entry
    -> očekujemo 400 + poruku da je period finalizovan
    """
    tenant_code = f"lock-cash-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    payload = {
        "entry_date": "2025-04-05",
        "kind": "income",
        "amount": "100.00",
        "description": "Test lock cash entry",
    }

    # --- CREATE cash entry ---
    # VAŽNO: /cash/ (sa kosom crtom) – ovo je kanonski path u postojećim testovima
    r = httpx.post(f"{BASE_URL}/cash/", json=payload, headers=headers, timeout=5)
    assert r.status_code == 201, r.text
    created = r.json()
    cash_id = created["id"]
    assert isinstance(cash_id, int)

    # --- FINALIZE mjeseca 2025-04 za ovog tenanta ---
    _finalize_month(tenant_code=tenant_code, year=2025, month=4)

    # --- DELETE nakon finalizacije -> treba da bude blokirano ---
    r = httpx.delete(
        f"{BASE_URL}/cash/{cash_id}", headers=headers, timeout=5
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert "detail" in body
    assert "Cannot modify data for finalized tax period 2025-04" in body["detail"]
