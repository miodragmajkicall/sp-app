import pytest
import time
from decimal import Decimal

pytestmark = pytest.mark.live_api

import httpx

BASE_URL = "http://localhost:8000"


def _headers_for_tenant(code: str) -> dict:
    return {"X-Tenant-Code": code}


def test_invoices_crud_flow():
    """
    Osnovni CRUD tok za fakture:
    - kreiramo fakturu sa 2 stavke
    - provjeravamo izračunate sume (osnovica, PDV, total)
    - dohvatamo fakturu po ID-u
    - listamo fakture za tenanta
    - brišemo fakturu i provjeravamo da vraća 404 nakon brisanja
    """
    tenant_code = f"inv-crud-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    payload = {
        "invoice_number": "2025-0001",
        "issue_date": "2025-01-10",
        "due_date": "2025-01-20",
        "buyer_name": "Test Kupac d.o.o.",
        "buyer_address": "Banja Luka, Kralja Petra I",
        "items": [
            {
                "description": "Usluga šišanja",
                "quantity": "2.00",
                "unit_price": "50.00",
                "vat_rate": "0.17",  # 17% PDV
            },
            {
                "description": "Pranje kose",
                "quantity": "1.00",
                "unit_price": "200.00",
                "vat_rate": "0.17",
            },
        ],
    }

    # --- CREATE ---
    r = httpx.post(f"{BASE_URL}/invoices/", json=payload, headers=headers, timeout=5)
    assert r.status_code == 201, r.text
    created = r.json()

    invoice_id = created["id"]
    assert isinstance(invoice_id, int)
    assert created["invoice_number"] == payload["invoice_number"]
    assert created["buyer_name"] == payload["buyer_name"]
    assert len(created["items"]) == 2

    # provjera suma
    total_base = Decimal(str(created["total_base"]))
    total_vat = Decimal(str(created["total_vat"]))
    total_amount = Decimal(str(created["total_amount"]))

    # ručni obračun:
    # stavka 1: 2 * 50 = 100, PDV 17 → 17, total 117
    # stavka 2: 1 * 200 = 200, PDV 34 → total 234
    # ukupno: base=300, vat=51, total=351
    assert total_base == Decimal("300.00")
    assert total_vat == Decimal("51.00")
    assert total_amount == Decimal("351.00")

    # --- GET BY ID ---
    r = httpx.get(f"{BASE_URL}/invoices/{invoice_id}", headers=headers, timeout=5)
    assert r.status_code == 200, r.text
    fetched = r.json()
    assert fetched["id"] == invoice_id
    assert fetched["invoice_number"] == payload["invoice_number"]
    assert len(fetched["items"]) == 2

    # --- LIST ---
    r = httpx.get(f"{BASE_URL}/invoices", headers=headers, timeout=5)
    assert r.status_code == 200, r.text
    items = r.json()
    assert any(inv["id"] == invoice_id for inv in items)

    # --- DELETE ---
    r = httpx.delete(f"{BASE_URL}/invoices/{invoice_id}", headers=headers, timeout=5)
    assert r.status_code == 204, r.text

    # --- GET nakon brisanja → 404 ---
    r = httpx.get(f"{BASE_URL}/invoices/{invoice_id}", headers=headers, timeout=5)
    assert r.status_code == 404


def test_invoices_list_filters_and_pagination():
    """
    Testiramo:
    - datumske filtere (issue_date)
    - filtriranje po buyer_name
    - paginaciju (limit/offset)
    """
    tenant_code = f"inv-list-{int(time.time())}"
    headers = _headers_for_tenant(tenant_code)

    # kreiramo 3 fakture sa različitim datumima i kupcima
    invoices_payloads = [
        {
            "invoice_number": "L-001",
            "issue_date": "2025-01-01",
            "due_date": "2025-01-10",
            "buyer_name": "Buyer A",
            "buyer_address": "Adresa A",
            "items": [
                {
                    "description": "Usluga A",
                    "quantity": "1.00",
                    "unit_price": "100.00",
                    "vat_rate": "0.17",
                }
            ],
        },
        {
            "invoice_number": "L-002",
            "issue_date": "2025-01-20",
            "due_date": "2025-01-30",
            "buyer_name": "Buyer B",
            "buyer_address": "Adresa B",
            "items": [
                {
                    "description": "Usluga B",
                    "quantity": "1.00",
                    "unit_price": "150.00",
                    "vat_rate": "0.17",
                }
            ],
        },
        {
            "invoice_number": "L-003",
            "issue_date": "2025-02-10",
            "due_date": "2025-02-20",
            "buyer_name": "Another Buyer",
            "buyer_address": "Adresa C",
            "items": [
                {
                    "description": "Usluga C",
                    "quantity": "1.00",
                    "unit_price": "200.00",
                    "vat_rate": "0.17",
                }
            ],
        },
    ]

    created_ids = []
    for payload in invoices_payloads:
        r = httpx.post(f"{BASE_URL}/invoices/", json=payload, headers=headers, timeout=5)
        assert r.status_code == 201, r.text
        created_ids.append(r.json()["id"])

    # --- DATUMSKI FILTER ---
    # od 2025-01-15 do 2025-01-31 treba da vrati samo fakturu sa issue_date 2025-01-20
    r = httpx.get(
        f"{BASE_URL}/invoices",
        params={"date_from": "2025-01-15", "date_to": "2025-01-31"},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["invoice_number"] == "L-002"

    # --- FILTER PO BUYER_NAME ---
    # buyer_name sadrži "Buyer" -> prve dvije fakture (Buyer A, Buyer B)
    r = httpx.get(
        f"{BASE_URL}/invoices",
        params={"buyer_name": "Buyer"},
        headers=headers,
        timeout=5,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    numbers = sorted(inv["invoice_number"] for inv in data)
    assert numbers == ["L-001", "L-002"]

    # --- PAGINACIJA ---
    # bez filtera, limit=1 offset=0 i offset=1 -> različiti ID-jevi
    r1 = httpx.get(
        f"{BASE_URL}/invoices",
        params={"limit": 1, "offset": 0},
        headers=headers,
        timeout=5,
    )
    r2 = httpx.get(
        f"{BASE_URL}/invoices",
        params={"limit": 1, "offset": 1},
        headers=headers,
        timeout=5,
    )
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    data1 = r1.json()
    data2 = r2.json()
    assert len(data1) == 1
    assert len(data2) == 1
    assert data1[0]["id"] != data2[0]["id"]


def test_invoice_number_unique_per_tenant():
    """
    Testiramo ograničenje:
    - isti invoice_number za ISTI tenant -> 409
    - isti invoice_number za DRUGI tenant -> dozvoljeno (201)
    """
    base_suffix = int(time.time())
    tenant1 = f"inv-uniq-{base_suffix}"
    tenant2 = f"inv-uniq-{base_suffix}-other"

    headers1 = _headers_for_tenant(tenant1)
    headers2 = _headers_for_tenant(tenant2)

    payload = {
        "invoice_number": "UNIQ-001",
        "issue_date": "2025-03-01",
        "due_date": "2025-03-10",
        "buyer_name": "Unique Buyer",
        "buyer_address": "Adresa X",
        "items": [
            {
                "description": "Usluga X",
                "quantity": "1.00",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
    }

    # tenant1, prvi put -> OK
    r = httpx.post(f"{BASE_URL}/invoices/", json=payload, headers=headers1, timeout=5)
    assert r.status_code == 201, r.text

    # tenant1, drugi put, isti invoice_number -> 409
    r = httpx.post(f"{BASE_URL}/invoices/", json=payload, headers=headers1, timeout=5)
    assert r.status_code == 409, r.text
    msg = r.json().get("detail", "").lower()
    assert "invoice number" in msg or "already exists" in msg

    # tenant2, isti invoice_number -> treba da prođe
    r = httpx.post(f"{BASE_URL}/invoices/", json=payload, headers=headers2, timeout=5)
    assert r.status_code == 201, r.text
