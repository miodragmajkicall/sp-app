# /home/miso/dev/sp-app/sp-app/tests/test_kpr.py
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TENANT = "kpr-test-tenant"
HEADERS = {"X-Tenant-Code": TENANT}

_data_created = False


def _ensure_sample_data() -> None:
    """
    Kreira minimalni skup podataka za KPR testove (samo jednom po test run-u):

    - 1 izlazna faktura (prihod),
    - 1 ulazna faktura (rashod),
    - 1 cash income,
    - 1 cash expense.

    Sve vezano za TENANT = 'kpr-test-tenant'.
    """
    global _data_created
    if _data_created:
        return

    # 1) Izlazna faktura (prihod)
    invoice_payload = {
        "invoice_number": "KPR-INV-001",
        "issue_date": "2025-01-15",
        "due_date": "2025-01-20",
        "buyer_name": "KPR Test Kupac",
        "buyer_address": "Adresa Kupca 1",
        "items": [
            {
                "description": "Usluga šišanja",
                "quantity": "1",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
    }
    resp = client.post("/invoices", json=invoice_payload, headers=HEADERS)
    # Ako već postoji (npr. ponovni run), može vratiti 409 – za testove je ok da
    # u tom slučaju samo nastavimo jer podaci već postoje.
    assert resp.status_code in (201, 409)

    # 2) Ulazna faktura (rashod – dobavljač)
    input_invoice_payload = {
        "supplier_name": "Elektrodistribucija KPR",
        "supplier_tax_id": "1234567890000",
        "supplier_address": "Ulica Broj 10, Banja Luka",
        "invoice_number": "KPR-INP-001",
        "issue_date": "2025-01-10",
        "due_date": "2025-01-25",
        "total_base": "50.00",
        "total_vat": "8.50",
        "total_amount": "58.50",
        "currency": "BAM",
        "note": "Račun za struju – januar.",
    }
    resp = client.post("/input-invoices", json=input_invoice_payload, headers=HEADERS)
    assert resp.status_code in (201, 409)

    # 3) Cash income
    cash_income_payload = {
        "entry_date": "2025-01-18",
        "kind": "income",
        "amount": "120.00",
        "note": "Gotovinska uplata u kasu (KPR test)",
    }
    resp = client.post("/cash/", json=cash_income_payload, headers=HEADERS)
    assert resp.status_code == 201

    # 4) Cash expense
    cash_expense_payload = {
        "entry_date": "2025-01-19",
        "kind": "expense",
        "amount": "30.00",
        "note": "Gotovinski rashod (KPR test)",
    }
    resp = client.post("/cash/", json=cash_expense_payload, headers=HEADERS)
    assert resp.status_code == 201

    _data_created = True


def test_kpr_list_basic_structure_and_counts():
    """
    Osnovni test za /kpr:

    - status 200,
    - JSON ima `total` i `items`,
    - ima barem par redova (prihodi + rashodi),
    - svaki red ima ključna polja (date, kind, category, amount, source, source_id).
    """
    _ensure_sample_data()

    resp = client.get("/kpr", headers=HEADERS)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, dict)
    assert "total" in data
    assert "items" in data

    total = data["total"]
    items = data["items"]

    assert isinstance(total, int)
    assert isinstance(items, list)
    assert total >= 2  # barem nešto treba da postoji
    assert len(items) >= 2

    first = items[0]
    # Ključna polja iz KprRowItem:
    for key in ("date", "kind", "category", "amount", "source", "source_id"):
        assert key in first

    assert first["kind"] in ("income", "expense")
    assert first["category"] in ("invoice", "input_invoice", "cash")


def test_kpr_list_year_month_filter():
    """
    Provjerava da year/month filter radi i da svi datumi koji se vrate
    upadaju u traženi mjesec i godinu.
    """
    _ensure_sample_data()

    resp = client.get(
        "/kpr?year=2025&month=1",
        headers=HEADERS,
    )
    assert resp.status_code == 200

    data = resp.json()
    items = data["items"]

    # Može biti 0+ – ali ako ih ima, svi moraju biti u januaru 2025.
    for row in items:
        date_str = row["date"]
        assert isinstance(date_str, str)
        assert date_str.startswith("2025-01-")


def test_kpr_export_pdf():
    """
    Testira PDF export za KPR:

    - status 200,
    - content-type PDF,
    - tijelo odgovora nije prazno.
    """
    _ensure_sample_data()

    resp = client.get("/kpr/export?year=2025&month=1", headers=HEADERS)
    assert resp.status_code == 200

    content_type = resp.headers.get("content-type", "")
    assert content_type.startswith("application/pdf")

    pdf_bytes = resp.content
    # Ne mora biti ogroman, ali svakako > 0
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 100
