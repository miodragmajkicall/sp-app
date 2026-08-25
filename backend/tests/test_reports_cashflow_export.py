# /home/miso/dev/sp-app/sp-app/backend/tests/test_reports_cashflow_export.py
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_reports_cashflow_export_csv_basic():
    response = client.get(
        "/reports/cashflow/2025/export",
        headers={"X-Tenant-Code": "t-demo"},
    )

    assert response.status_code == 200

    # Content-Type treba da bude text/csv (može imati charset suffix)
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/csv")

    # Content-Disposition sa očekivanim imenom fajla
    content_disposition = response.headers.get("content-disposition", "")
    assert 'attachment; filename="cashflow-t-demo-2025.csv"' in content_disposition

    # Tijelo CSV-a
    body = response.content.decode("utf-8")
    lines = [line for line in body.strip().splitlines() if line]

    # Header + 12 mjeseci
    assert len(lines) == 13
    assert lines[0] == "year,month,tenant_code,income,expense,profit,currency"

    # Prvi podatak (januar) – osnovna provjera formata
    first_data = lines[1].split(",")
    assert first_data[0] == "2025"           # year
    assert first_data[1].isdigit()          # month
    assert first_data[2] == "t-demo"        # tenant_code
    # income/expense/profit mogu biti "0" ili "0.00" – samo provjeravamo da postoje
    assert len(first_data) == 7

def test_reports_cashflow_uses_actual_cash_entries_and_includes_linked_payment_once():
    tenant = f"reports-cashflow-{uuid4().hex[:12]}"
    other_tenant = f"reports-cashflow-other-{uuid4().hex[:12]}"
    headers = {"X-Tenant-Code": tenant}
    other_headers = {"X-Tenant-Code": other_tenant}

    cash_income = client.post(
        "/cash/",
        headers=headers,
        json={
            "entry_date": "2026-08-19",
            "kind": "income",
            "amount": "50.00",
            "note": "Independent cash income",
        },
    )
    assert cash_income.status_code == 201, cash_income.text

    cash_expense = client.post(
        "/cash/",
        headers=headers,
        json={
            "entry_date": "2026-08-20",
            "kind": "expense",
            "amount": "30.00",
            "note": "Independent cash expense",
        },
    )
    assert cash_expense.status_code == 201, cash_expense.text

    unpaid_invoice = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "Unpaid Supplier",
            "invoice_number": f"UNPAID-{uuid4().hex[:8]}",
            "issue_date": "2026-05-10",
            "posting_date": "2026-05-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert unpaid_invoice.status_code == 201, unpaid_invoice.text

    paid_invoice = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "Paid Supplier",
            "invoice_number": f"PAID-{uuid4().hex[:8]}",
            "issue_date": "2026-05-12",
            "posting_date": "2026-05-12",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert paid_invoice.status_code == 201, paid_invoice.text

    payment = client.post(
        f"/input-invoices/{paid_invoice.json()['id']}/payment",
        headers=headers,
        json={
            "payment_date": "2026-08-18",
            "account": "bank",
        },
    )
    assert payment.status_code == 201, payment.text

    foreign_expense = client.post(
        "/cash/",
        headers=other_headers,
        json={
            "entry_date": "2026-08-21",
            "kind": "expense",
            "amount": "999.00",
            "note": "Foreign tenant expense",
        },
    )
    assert foreign_expense.status_code == 201, foreign_expense.text

    response = client.get(
        "/reports/cashflow/2026",
        headers=headers,
    )
    assert response.status_code == 200, response.text

    items = {item["month"]: item for item in response.json()["items"]}

    may = items[5]
    assert Decimal(str(may["income"])) == Decimal("0.00")
    assert Decimal(str(may["expense"])) == Decimal("0.00")
    assert Decimal(str(may["profit"])) == Decimal("0.00")

    august = items[8]
    assert Decimal(str(august["income"])) == Decimal("50.00")
    assert Decimal(str(august["expense"])) == Decimal("147.00")
    assert Decimal(str(august["profit"])) == Decimal("-97.00")

    export = client.get(
        "/reports/cashflow/2026/export",
        headers=headers,
    )
    assert export.status_code == 200, export.text

    lines = [
        line
        for line in export.content.decode("utf-8").strip().splitlines()
        if line
    ]
    august_csv = lines[8].split(",")

    assert august_csv[0] == "2026"
    assert august_csv[1] == "8"
    assert august_csv[2] == tenant
    assert Decimal(august_csv[3]) == Decimal("50.00")
    assert Decimal(august_csv[4]) == Decimal("147.00")
    assert Decimal(august_csv[5]) == Decimal("-97.00")
    assert august_csv[6] == "BAM"
