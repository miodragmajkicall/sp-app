from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import CashEntry, Invoice, TaxMonthlyResult
from app.tenant_security import ensure_tenant_exists


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers(prefix: str) -> dict[str, str]:
    return {"X-Tenant-Code": f"{uuid4().hex[:10]}-{prefix}"}


def _create_invoice(
    tenant_code: str,
    *,
    issue_date: date = date(2026, 5, 10),
    total_amount: Decimal = Decimal("117.00"),
    is_paid: bool = False,
) -> int:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant_code)

        suffix = uuid4().hex[:10]
        invoice = Invoice(
            tenant_code=tenant_code,
            invoice_number=f"PAY-{suffix}",
            issue_date=issue_date,
            buyer_name=f"Payment buyer {suffix}",
            total_base=Decimal("100.00"),
            total_vat=total_amount - Decimal("100.00"),
            total_amount=total_amount,
            is_paid=is_paid,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        return invoice.id


def _finalize_month(
    tenant_code: str,
    *,
    year: int,
    month: int,
) -> None:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant_code)

        db.add(
            TaxMonthlyResult(
                tenant_code=tenant_code,
                year=year,
                month=month,
                total_income=Decimal("0.00"),
                total_expense=Decimal("0.00"),
                taxable_base=Decimal("0.00"),
                income_tax=Decimal("0.00"),
                contributions_total=Decimal("0.00"),
                total_due=Decimal("0.00"),
                currency="BAM",
                is_final=True,
            )
        )
        db.commit()


def _create_payment(
    client: TestClient,
    headers: dict[str, str],
    invoice_id: int,
    *,
    payment_date: str = "2026-08-27",
    account: str = "bank",
    note: str = "Output payment lifecycle test",
):
    return client.post(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
        json={
            "payment_date": payment_date,
            "account": account,
            "note": note,
        },
    )


def test_create_payment_creates_income_cash_entry_and_marks_invoice_paid(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-create")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    response = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-27",
        account="bank",
        note="Naplata kupca",
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["payment_date"] == "2026-08-27"
    assert data["account"] == "bank"
    assert Decimal(data["amount"]) == Decimal("117.00")
    assert data["note"] == "Naplata kupca"

    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True

        payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == tenant,
                CashEntry.invoice_id == invoice_id,
            )
        ).scalar_one()

        assert payment.id == data["id"]
        assert payment.entry_date == date(2026, 8, 27)
        assert payment.kind == "income"
        assert payment.amount == Decimal("117.00")
        assert payment.account == "bank"
        assert payment.invoice_id == invoice_id
        assert payment.input_invoice_id is None
        assert payment.description == "Naplata kupca"


def test_get_payment_returns_existing_payment(client: TestClient) -> None:
    headers = _headers("output-payment-get")
    invoice_id = _create_invoice(headers["X-Tenant-Code"])

    created = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-27",
        account="cash",
        note="GET output payment",
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == created.json()


def test_duplicate_payment_is_rejected_and_only_one_cash_entry_exists(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-duplicate")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(tenant)

    first = _create_payment(client, headers, invoice_id)
    second = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-28",
        account="cash",
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json() == {"detail": "Invoice payment already exists"}

    with SessionLocal() as db:
        count = db.execute(
            select(func.count(CashEntry.id)).where(
                CashEntry.tenant_code == tenant,
                CashEntry.invoice_id == invoice_id,
            )
        ).scalar_one()

    assert count == 1


def test_payment_is_tenant_scoped(client: TestClient) -> None:
    owner = _headers("output-payment-owner")
    other = _headers("output-payment-other")
    invoice_id = _create_invoice(owner["X-Tenant-Code"])

    cross_tenant = _create_payment(client, other, invoice_id)

    assert cross_tenant.status_code == 404
    assert cross_tenant.json() == {"detail": "Invoice not found"}


def test_delete_payment_removes_cash_entry_and_marks_invoice_unpaid(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(tenant)

    created = _create_payment(client, headers, invoice_id)
    assert created.status_code == 201, created.text

    deleted = client.delete(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert deleted.status_code == 204, deleted.text

    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is False

        payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == tenant,
                CashEntry.invoice_id == invoice_id,
            )
        ).scalar_one_or_none()

        assert payment is None


def test_create_payment_is_blocked_in_finalized_payment_month(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-finalized-create")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(tenant)

    _finalize_month(tenant, year=2026, month=8)

    response = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-27",
    )

    assert response.status_code == 400, response.text
    assert (
        "Cannot modify data for finalized tax period 2026-08"
        in response.json()["detail"]
    )


def test_delete_payment_is_blocked_in_finalized_payment_month(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-finalized-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(tenant)

    created = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-09-05",
    )
    assert created.status_code == 201, created.text

    _finalize_month(tenant, year=2026, month=9)

    response = client.delete(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert response.status_code == 400, response.text
    assert (
        "Cannot modify data for finalized tax period 2026-09"
        in response.json()["detail"]
    )


def test_open_payment_month_is_allowed_when_invoice_issue_month_is_finalized(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-finalized-issue")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )

    _finalize_month(tenant, year=2026, month=5)

    response = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-27",
    )

    assert response.status_code == 201, response.text
    assert response.json()["payment_date"] == "2026-08-27"


def test_legacy_mark_paid_is_rejected_without_changing_payment_state(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-legacy")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(tenant)

    response = client.post(
        f"/invoices/{invoice_id}/mark-paid",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "Invoice payments must be created through the "
            "invoice payment endpoint"
        )
    }

    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is False

        payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == tenant,
                CashEntry.invoice_id == invoice_id,
            )
        ).scalar_one_or_none()

        assert payment is None


def test_invoice_with_existing_payment_cannot_be_deleted(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-invoice-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_invoice(tenant)

    payment = _create_payment(client, headers, invoice_id)
    assert payment.status_code == 201, payment.text

    response = client.delete(
        f"/invoices/{invoice_id}",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "Invoice with an existing payment cannot be deleted; "
            "remove the payment first"
        )
    }

    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True

        linked_payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == tenant,
                CashEntry.invoice_id == invoice_id,
            )
        ).scalar_one()

        assert linked_payment.id == payment.json()["id"]


def test_output_payment_is_not_double_counted_in_kpr(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-kpr")
    invoice_id = _create_invoice(
        headers["X-Tenant-Code"],
        issue_date=date(2026, 8, 10),
        total_amount=Decimal("117.00"),
    )

    payment = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-27",
    )
    assert payment.status_code == 201, payment.text

    response = client.get(
        "/kpr?year=2026&month=8",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    invoice_rows = [
        row
        for row in data["items"]
        if row["source"] == "invoice"
        and row["source_id"] == invoice_id
    ]
    assert len(invoice_rows) == 1
    assert Decimal(str(invoice_rows[0]["amount"])) == Decimal("117.00")

    assert not any(
        row["source"] == "cash"
        and row["source_id"] == payment.json()["id"]
        for row in data["items"]
    )


def test_output_payment_is_not_double_counted_in_tax_auto(
    client: TestClient,
) -> None:
    headers = _headers("output-payment-tax")
    invoice_id = _create_invoice(
        headers["X-Tenant-Code"],
        issue_date=date(2026, 8, 10),
        total_amount=Decimal("117.00"),
    )

    payment = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-27",
    )
    assert payment.status_code == 201, payment.text

    response = client.get(
        "/tax/monthly/auto",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_income"])) == Decimal("117.00")
