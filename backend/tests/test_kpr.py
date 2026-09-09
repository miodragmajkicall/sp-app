# /home/miso/dev/sp-app/sp-app/tests/test_kpr.py
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import TenantTaxProfileSettings
from app.tenant_security import ensure_tenant_exists
from tests.invoice_profile_helpers import save_complete_profile

client = TestClient(app)

TENANT = "kpr-test-tenant"
HEADERS = {"X-Tenant-Code": TENANT}

_data_created = False


def _set_cash_profile(tenant: str) -> None:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant)
        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant,
                entity="RS",
                regime="pausal",
                scenario_key="rs_primary",
                has_additional_activity=False,
            )
        )
        db.commit()


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
    save_complete_profile(client, HEADERS)

    tax_profile = client.put(
        "/settings/tax",
        headers=HEADERS,
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
        },
    )
    assert tax_profile.status_code == 200, tax_profile.text

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

def test_kpr_input_invoice_payment_is_not_double_counted_and_keeps_tax_flag():
    tenant = f"kpr-input-payment-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    _set_cash_profile(tenant)

    input_invoice_payload = {
        "supplier_name": "KPR Payment Test Supplier",
        "supplier_tax_id": "1234567890000",
        "supplier_address": "Banja Luka",
        "invoice_number": f"KPR-PAY-{uuid4().hex[:8]}",
        "issue_date": "2026-08-10",
        "due_date": "2026-08-20",
        "posting_date": "2026-08-10",
        "is_tax_deductible": False,
        "total_base": "100.00",
        "total_vat": "17.00",
        "total_amount": "117.00",
        "note": "KPR regression test",
    }

    create_resp = client.post(
        "/input-invoices",
        json=input_invoice_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    input_invoice = create_resp.json()
    input_invoice_id = input_invoice["id"]

    payment_resp = client.post(
        f"/input-invoices/{input_invoice_id}/payment",
        json={
            "payment_date": "2026-08-18",
            "account": "bank",
            "note": "Plaćanje KPR regression testa",
        },
        headers=headers,
    )
    assert payment_resp.status_code == 201, payment_resp.text

    kpr_resp = client.get(
        "/kpr?year=2026&month=8",
        headers=headers,
    )
    assert kpr_resp.status_code == 200, kpr_resp.text

    data = kpr_resp.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1

    row = data["items"][0]

    assert row["source"] == "input_invoice"
    assert row["source_id"] == input_invoice_id
    assert row["kind"] == "expense"
    assert Decimal(str(row["amount"])) == Decimal("117.00")
    assert row["tax_deductible"] is False


def test_kpr_cash_basis_invoice_is_recognized_only_in_payment_month():
    tenant = f"kpr-recognition-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    _set_cash_profile(tenant)

    create_resp = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "Recognition Supplier",
            "invoice_number": f"KPR-REC-{uuid4().hex[:8]}",
            "issue_date": "2026-05-10",
            "posting_date": "2026-05-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    invoice_id = create_resp.json()["id"]

    may = client.get("/kpr?year=2026&month=5", headers=headers)
    assert may.status_code == 200, may.text
    assert not any(row["source_id"] == invoice_id for row in may.json()["items"])

    payment = client.post(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
        json={"payment_date": "2026-08-18", "account": "bank"},
    )
    assert payment.status_code == 201, payment.text

    august = client.get("/kpr?year=2026&month=8", headers=headers)
    assert august.status_code == 200, august.text
    invoice_rows = [row for row in august.json()["items"] if row["source_id"] == invoice_id]
    assert len(invoice_rows) == 1
    assert invoice_rows[0]["date"] == "2026-08-18"


def test_kpr_manual_cash_exposes_tax_treatment_contract():
    tenant = f"kpr-cash-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    _set_cash_profile(tenant)

    payloads = [
        {
            "entry_date": "2026-08-19",
            "kind": "expense",
            "amount": "30.00",
            "recognition_class": "business_activity",
            "tax_treatment": "deductible",
            "note": "Deductible expense",
        },
        {
            "entry_date": "2026-08-20",
            "kind": "expense",
            "amount": "40.00",
            "recognition_class": "business_activity",
            "tax_treatment": "nondeductible",
            "note": "Nondeductible expense",
        },
        {
            "entry_date": "2026-08-21",
            "kind": "expense",
            "amount": "50.00",
            "recognition_class": "business_activity",
            "tax_treatment": "unresolved",
            "note": "Unresolved expense",
        },
        {
            "entry_date": "2026-08-22",
            "kind": "income",
            "amount": "60.00",
            "recognition_class": "business_activity",
            "note": "Recognized income",
        },
    ]

    created_ids = []
    for payload in payloads:
        response = client.post(
            "/cash/",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    kpr = client.get("/kpr?year=2026&month=8", headers=headers)
    assert kpr.status_code == 200, kpr.text

    rows_by_id = {
        row["source_id"]: row
        for row in kpr.json()["items"]
        if row["source"] == "cash" and row["source_id"] in created_ids
    }
    assert len(rows_by_id) == 4

    deductible = rows_by_id[created_ids[0]]
    assert deductible["tax_treatment"] == "deductible"
    assert deductible["tax_deductible"] is True

    nondeductible = rows_by_id[created_ids[1]]
    assert nondeductible["tax_treatment"] == "nondeductible"
    assert nondeductible["tax_deductible"] is False

    unresolved = rows_by_id[created_ids[2]]
    assert unresolved["tax_treatment"] == "unresolved"
    assert unresolved["tax_deductible"] is False

    income = rows_by_id[created_ids[3]]
    assert income["kind"] == "income"
    assert income["tax_treatment"] is None
    assert income["tax_deductible"] is False

    export = client.get(
        "/kpr/export-excel?year=2026&month=8",
        headers=headers,
    )
    assert export.status_code == 200, export.text

    csv_text = export.content.decode("utf-8-sig")
    assert "tax_treatment" in csv_text
    assert "deductible" in csv_text
    assert "nondeductible" in csv_text
    assert "unresolved" in csv_text


def test_kpr_cash_only_entry_is_not_recognized():
    tenant = f"kpr-cash-only-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}

    response = client.post(
        "/cash/",
        headers=headers,
        json={
            "entry_date": "2026-08-19",
            "kind": "income",
            "amount": "45.00",
            "recognition_class": "cash_only",
            "note": "Cashflow only",
        },
    )
    assert response.status_code == 201, response.text

    kpr = client.get("/kpr?year=2026&month=8", headers=headers)
    assert kpr.status_code == 200, kpr.text
    assert not any(
        row["source"] == "cash" and row["source_id"] == response.json()["id"]
        for row in kpr.json()["items"]
    )


def test_kpr_business_activity_cash_with_unresolved_context_fails_closed():
    tenant = f"kpr-cash-unresolved-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}

    response = client.post(
        "/cash/",
        headers=headers,
        json={
            "entry_date": "2026-08-19",
            "kind": "income",
            "amount": "45.00",
            "recognition_class": "business_activity",
            "note": "Unsupported recognition context",
        },
    )
    assert response.status_code == 201, response.text

    kpr = client.get("/kpr?year=2026&month=8", headers=headers)
    assert kpr.status_code == 409, kpr.text
    assert (
        "Manual cash recognition policy is not configured"
        in kpr.json()["detail"]
    )


def test_kpr_unresolved_context_does_not_fall_back_to_issue_date():
    tenant = f"kpr-unresolved-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    create_resp = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "Unsupported Supplier",
            "invoice_number": f"KPR-UNR-{uuid4().hex[:8]}",
            "issue_date": "2026-05-10",
            "posting_date": "2026-05-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert create_resp.status_code == 201, create_resp.text

    kpr = client.get("/kpr?year=2026&month=5", headers=headers)
    assert kpr.status_code == 200, kpr.text
    assert not any(
        row["source_id"] == create_resp.json()["id"] for row in kpr.json()["items"]
    )

def test_kpr_paid_input_invoice_with_unresolved_context_fails_closed():
    tenant = f"kpr-unresolved-paid-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}

    create_resp = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "Unsupported Paid Supplier",
            "invoice_number": f"KPR-UNR-PAID-{uuid4().hex[:8]}",
            "issue_date": "2026-05-10",
            "posting_date": "2026-05-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    invoice_id = create_resp.json()["id"]

    payment = client.post(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
        json={"payment_date": "2026-08-18", "account": "bank"},
    )
    assert payment.status_code == 201, payment.text

    kpr = client.get("/kpr?year=2026&month=8", headers=headers)
    assert kpr.status_code == 409, kpr.text
    assert (
        "recognition policy is not configured"
        in kpr.json()["detail"]
    )


def test_kpr_global_order_and_pagination():
    tenant = f"kpr-order-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    save_complete_profile(client, headers)
    _set_cash_profile(tenant)

    invoice = client.post(
        "/invoices",
        headers=headers,
        json={
            "invoice_number": f"KPR-ORDER-{uuid4().hex[:8]}",
            "issue_date": "2026-09-10",
            "due_date": "2026-09-20",
            "buyer_name": "KPR Order Kupac",
            "buyer_address": "Banja Luka",
            "items": [
                {
                    "description": "KPR order test",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "vat_rate": "0.17",
                }
            ],
        },
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]

    input_invoice = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "KPR Order Supplier",
            "invoice_number": f"KPR-INP-{uuid4().hex[:8]}",
            "issue_date": "2026-08-30",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert input_invoice.status_code == 201, input_invoice.text
    input_id = input_invoice.json()["id"]

    payment = client.post(
        f"/input-invoices/{input_id}/payment",
        headers=headers,
        json={
            "payment_date": "2026-09-08",
            "account": "bank",
        },
    )
    assert payment.status_code == 201, payment.text

    cash_ids = []
    for entry_date in (
        "2026-09-05",
        "2026-09-10",
        "2026-09-10",
        "2026-09-12",
    ):
        response = client.post(
            "/cash/",
            headers=headers,
            json={
                "entry_date": entry_date,
                "kind": "income",
                "amount": "10.00",
                "recognition_class": "business_activity",
                "note": "KPR pagination test",
            },
        )
        assert response.status_code == 201, response.text
        cash_ids.append(response.json()["id"])

    expected = [
        ("2026-09-05", "cash", cash_ids[0]),
        ("2026-09-08", "input_invoice", input_id),
        ("2026-09-10", "cash", cash_ids[1]),
        ("2026-09-10", "cash", cash_ids[2]),
        ("2026-09-10", "invoice", invoice_id),
        ("2026-09-12", "cash", cash_ids[3]),
    ]

    def row_keys(items):
        return [
            (row["date"], row["source"], row["source_id"])
            for row in items
        ]

    base_url = "/kpr?year=2026&month=9"

    full = client.get(
        f"{base_url}&limit=100&offset=0",
        headers=headers,
    )
    assert full.status_code == 200, full.text
    assert full.json()["total"] == 6
    assert row_keys(full.json()["items"]) == expected

    paged_items = []
    for offset in (0, 2, 4):
        response = client.get(
            f"{base_url}&limit=2&offset={offset}",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 6
        assert len(response.json()["items"]) == 2
        paged_items.extend(response.json()["items"])

    assert row_keys(paged_items) == expected
    assert len(set(row_keys(paged_items))) == 6

    empty_page = client.get(
        f"{base_url}&limit=2&offset=6",
        headers=headers,
    )
    assert empty_page.status_code == 200, empty_page.text
    assert empty_page.json()["total"] == 6
    assert empty_page.json()["items"] == []

    repeated = client.get(
        f"{base_url}&limit=2&offset=2",
        headers=headers,
    )
    assert repeated.status_code == 200, repeated.text
    assert row_keys(repeated.json()["items"]) == expected[2:4]


def test_kpr_kind_filter_before_pagination():
    tenant = f"kpr-kind-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    _set_cash_profile(tenant)

    scenarios = [
        ("2026-09-01", "income", "10.00", None),
        ("2026-09-02", "expense", "20.00", "deductible"),
        ("2026-09-03", "income", "30.00", None),
        ("2026-09-04", "expense", "40.00", "unresolved"),
    ]

    created_ids = []
    for entry_date, kind, amount, treatment in scenarios:
        payload = {
            "entry_date": entry_date,
            "kind": kind,
            "amount": amount,
            "recognition_class": "business_activity",
            "note": "KPR kind filter test",
        }
        if treatment is not None:
            payload["tax_treatment"] = treatment

        response = client.post("/cash/", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    cash_only = client.post(
        "/cash/",
        headers=headers,
        json={
            "entry_date": "2026-09-05",
            "kind": "expense",
            "amount": "999.00",
            "recognition_class": "cash_only",
            "note": "Excluded cashflow",
        },
    )
    assert cash_only.status_code == 201, cash_only.text

    base_url = "/kpr?year=2026&month=9"

    def get_rows(query):
        response = client.get(f"{base_url}{query}", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    full = get_rows("&limit=100&offset=0")
    assert full["total"] == 4
    assert [row["source_id"] for row in full["items"]] == created_ids

    income = get_rows("&kind=income&limit=1&offset=0")
    assert income["total"] == 2
    assert [row["source_id"] for row in income["items"]] == [created_ids[0]]

    income_page_2 = get_rows("&kind=income&limit=1&offset=1")
    assert income_page_2["total"] == 2
    assert [row["source_id"] for row in income_page_2["items"]] == [created_ids[2]]

    expense = get_rows("&kind=expense&limit=1&offset=0")
    assert expense["total"] == 2
    assert [row["source_id"] for row in expense["items"]] == [created_ids[1]]
    assert expense["items"][0]["tax_treatment"] == "deductible"

    expense_page_2 = get_rows("&kind=expense&limit=1&offset=1")
    assert expense_page_2["total"] == 2
    assert [row["source_id"] for row in expense_page_2["items"]] == [created_ids[3]]
    assert expense_page_2["items"][0]["tax_treatment"] == "unresolved"

    empty_page = get_rows("&kind=expense&limit=1&offset=2")
    assert empty_page["total"] == 2
    assert empty_page["items"] == []

    for invalid_kind in ("other", "INCOME"):
        response = client.get(
            f"{base_url}&kind={invalid_kind}",
            headers=headers,
        )
        assert response.status_code == 422, response.text


def test_kpr_summary_is_independent_of_kind_and_pagination():
    tenant = f"kpr-summary-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    _set_cash_profile(tenant)

    scenarios = [
        ("2026-09-01", "income", "10.00", None),
        ("2026-09-02", "expense", "20.00", "deductible"),
        ("2026-09-03", "expense", "30.00", "unresolved"),
    ]

    created_ids = []
    for entry_date, kind, amount, treatment in scenarios:
        payload = {
            "entry_date": entry_date,
            "kind": kind,
            "amount": amount,
            "recognition_class": "business_activity",
            "note": "KPR summary test",
        }
        if treatment is not None:
            payload["tax_treatment"] = treatment

        response = client.post("/cash/", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    cash_only = client.post(
        "/cash/",
        headers=headers,
        json={
            "entry_date": "2026-09-04",
            "kind": "expense",
            "amount": "999.00",
            "recognition_class": "cash_only",
            "note": "Excluded cashflow",
        },
    )
    assert cash_only.status_code == 201, cash_only.text

    expected_summary = {
        "income": Decimal("10.00"),
        "expense": Decimal("50.00"),
        "net": Decimal("-40.00"),
    }

    def assert_summary(data, expected):
        assert {
            key: Decimal(str(value))
            for key, value in data["summary"].items()
        } == expected

    base_url = "/kpr?year=2026&month=9"

    cases = [
        ("&limit=100&offset=0", 3, created_ids),
        ("&limit=1&offset=0", 3, [created_ids[0]]),
        ("&limit=1&offset=2", 3, [created_ids[2]]),
        ("&kind=income&limit=1&offset=0", 1, [created_ids[0]]),
        ("&kind=expense&limit=1&offset=0", 2, [created_ids[1]]),
        ("&kind=expense&limit=1&offset=1", 2, [created_ids[2]]),
        ("&kind=expense&limit=1&offset=2", 2, []),
    ]

    for query, expected_total, expected_ids in cases:
        response = client.get(f"{base_url}{query}", headers=headers)
        assert response.status_code == 200, response.text

        data = response.json()
        assert data["total"] == expected_total
        assert [row["source_id"] for row in data["items"]] == expected_ids
        assert_summary(data, expected_summary)

    empty = client.get(
        "/kpr?year=2026&month=10&limit=1&offset=0",
        headers=headers,
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []
    assert_summary(
        empty.json(),
        {
            "income": Decimal("0.00"),
            "expense": Decimal("0.00"),
            "net": Decimal("0.00"),
        },
    )

def test_kpr_csv_export_full_period_and_format():
    import csv
    from io import StringIO

    tenant = f"kpr-csv-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    _set_cash_profile(tenant)

    special_note = 'Čačak, ćirilica, šuma, žito, đak "navodnici"\nDrugi red'
    scenarios = [
        ("2026-01-10", "income", "1.00", None, special_note),
        *[
            (f"2026-09-{day:02d}", "income", "1.00", None, "CSV income")
            for day in range(1, 27)
        ],
        ("2026-09-27", "expense", "2.00", "deductible", "Odbitno"),
        ("2026-09-28", "expense", "3.00", "nondeductible", "Neodbitno"),
        ("2026-09-29", "expense", "4.00", "unresolved", "Nerazriješeno"),
    ]

    records = []
    for entry_date, kind, amount, treatment, note in scenarios:
        payload = {
            "entry_date": entry_date,
            "kind": kind,
            "amount": amount,
            "recognition_class": "business_activity",
            "note": note,
        }
        if treatment is not None:
            payload["tax_treatment"] = treatment

        response = client.post("/cash/", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        records.append((*scenarios[len(records)], str(response.json()["id"])))

    for entry_date, recognition_class in (
        ("2026-09-30", "cash_only"),
        ("2027-01-01", "business_activity"),
    ):
        response = client.post(
            "/cash/",
            headers=headers,
            json={
                "entry_date": entry_date,
                "kind": "income",
                "amount": "999.00",
                "recognition_class": recognition_class,
                "note": "Outside selected KPR scope",
            },
        )
        assert response.status_code == 201, response.text

    expected_ids = [record[5] for record in records]

    full = client.get(
        "/kpr?year=2026&limit=10000&offset=0",
        headers=headers,
    )
    assert full.status_code == 200, full.text
    data = full.json()
    assert data["total"] == 30
    assert [str(row["source_id"]) for row in data["items"]] == expected_ids
    assert {
        key: Decimal(str(value))
        for key, value in data["summary"].items()
    } == {
        "income": Decimal("27.00"),
        "expense": Decimal("9.00"),
        "net": Decimal("18.00"),
    }

    first = client.get(
        "/kpr?year=2026&limit=25&offset=0", headers=headers
    )
    second = client.get(
        "/kpr?year=2026&limit=25&offset=25", headers=headers
    )
    assert first.status_code == second.status_code == 200
    assert [
        str(row["source_id"])
        for row in first.json()["items"] + second.json()["items"]
    ] == expected_ids

    columns = [
        "datum", "vrsta", "kategorija", "kupac_dobavljac",
        "dok_broj", "opis", "iznos", "valuta", "poreski_priznat",
        "tax_treatment", "source", "source_id",
    ]

    expected_rows = [
        [
            entry_date,
            "PRIHOD" if kind == "income" else "RASHOD",
            "cash", "", "", note, f"{Decimal(amount):.2f}", "BAM",
            "DA" if treatment == "deductible" else "NE",
            treatment or "", "cash", source_id,
        ]
        for entry_date, kind, amount, treatment, note, source_id in records
    ]

    def read_csv(params):
        response = client.get(
            "/kpr/export-excel", headers=headers, params=params
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/csv")

        raw = response.content
        assert raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(StringIO(text, newline="")))

        assert rows[0] == columns
        assert all(len(row) == 12 for row in rows)
        assert text.endswith("\r\n")
        assert raw.count(b"\r\n") == len(rows)
        return raw, rows

    annual_bytes, annual_rows = read_csv({"year": 2026})
    assert annual_rows == [columns, *expected_rows]
    assert len({row[11] for row in annual_rows[1:]}) == 30

    _, monthly_rows = read_csv({"year": 2026, "month": 9})
    assert monthly_rows == [
        columns,
        *[row for row in expected_rows if row[0].startswith("2026-09-")],
    ]

    filtered_bytes, filtered_rows = read_csv({
        "year": 2026,
        "kind": "expense",
        "limit": 1,
        "offset": 25,
    })
    assert filtered_bytes == annual_bytes
    assert filtered_rows == annual_rows

    _, empty_rows = read_csv({"year": 2028})
    assert empty_rows == [columns]
