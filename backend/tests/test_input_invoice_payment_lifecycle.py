from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import CashEntry, InputInvoice, TaxMonthlyResult
from app.tenant_security import ensure_tenant_exists


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers(prefix: str) -> dict[str, str]:
    return {"X-Tenant-Code": f"{uuid4().hex[:10]}-{prefix}"}


def _create_input_invoice(
    tenant_code: str,
    *,
    issue_date: date = date(2026, 5, 10),
    total_amount: Decimal = Decimal("117.00"),
    is_paid: bool = False,
) -> int:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant_code)

        suffix = uuid4().hex[:10]
        invoice = InputInvoice(
            tenant_code=tenant_code,
            supplier_name=f"Payment supplier {suffix}",
            invoice_number=f"PAY-{suffix}",
            issue_date=issue_date,
            posting_date=issue_date,
            total_base=Decimal("100.00"),
            total_vat=total_amount - Decimal("100.00"),
            total_amount=total_amount,
            currency="BAM",
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
    payment_date: str = "2026-08-18",
    account: str = "bank",
    note: str = "Payment lifecycle test",
):
    return client.post(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
        json={
            "payment_date": payment_date,
            "account": account,
            "note": note,
        },
    )


def test_create_payment_creates_cash_entry_and_marks_invoice_paid(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-create")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_input_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    response = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-18",
        account="bank",
        note="Plaćanje dobavljaču",
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["payment_date"] == "2026-08-18"
    assert data["account"] == "bank"
    assert Decimal(data["amount"]) == Decimal("117.00")
    assert data["note"] == "Plaćanje dobavljaču"

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True

        payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == tenant,
                CashEntry.input_invoice_id == invoice_id,
            )
        ).scalar_one()

        assert payment.id == data["id"]
        assert payment.entry_date == date(2026, 8, 18)
        assert payment.kind == "expense"
        assert payment.amount == Decimal("117.00")
        assert payment.account == "bank"
        assert payment.invoice_id is None
        assert payment.input_invoice_id == invoice_id
        assert payment.description == "Plaćanje dobavljaču"

def test_get_payment_returns_existing_payment(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-get")
    invoice_id = _create_input_invoice(
        headers["X-Tenant-Code"],
        total_amount=Decimal("117.00"),
    )

    created = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-18",
        account="bank",
        note="GET payment detail test",
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["id"] == created.json()["id"]
    assert data["payment_date"] == "2026-08-18"
    assert data["account"] == "bank"
    assert Decimal(data["amount"]) == Decimal("117.00")
    assert data["note"] == "GET payment detail test"


def test_get_payment_returns_404_for_unpaid_invoice(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-get-unpaid")
    invoice_id = _create_input_invoice(
        headers["X-Tenant-Code"],
    )

    response = client.get(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {
        "detail": "Input invoice payment not found"
    }


def test_get_payment_is_tenant_isolated(
    client: TestClient,
) -> None:
    owner_headers = _headers("input-payment-get-owner")
    requester_headers = _headers("input-payment-get-requester")

    invoice_id = _create_input_invoice(
        owner_headers["X-Tenant-Code"],
    )

    created = _create_payment(
        client,
        owner_headers,
        invoice_id,
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"/input-invoices/{invoice_id}/payment",
        headers=requester_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {
        "detail": "Input invoice not found"
    }

def test_duplicate_payment_is_rejected(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-duplicate")
    invoice_id = _create_input_invoice(headers["X-Tenant-Code"])

    first = _create_payment(client, headers, invoice_id)
    second = _create_payment(client, headers, invoice_id)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json() == {
        "detail": "Input invoice payment already exists"
    }


def test_payment_is_tenant_isolated(
    client: TestClient,
) -> None:
    owner_headers = _headers("input-payment-owner")
    requester_headers = _headers("input-payment-requester")

    invoice_id = _create_input_invoice(
        owner_headers["X-Tenant-Code"]
    )

    response = _create_payment(
        client,
        requester_headers,
        invoice_id,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {
        "detail": "Input invoice not found"
    }


def test_payment_is_rejected_for_finalized_payment_month(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-finalized-create")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )
    _finalize_month(
        tenant,
        year=2026,
        month=8,
    )

    response = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-18",
    )

    assert response.status_code == 400, response.text

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is False

        payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == tenant,
                CashEntry.input_invoice_id == invoice_id,
            )
        ).scalar_one_or_none()

        assert payment is None


def test_payment_can_update_status_when_invoice_month_is_finalized(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-old-invoice")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )

    _finalize_month(
        tenant,
        year=2026,
        month=5,
    )

    response = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-18",
    )

    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True


def test_delete_payment_removes_cash_entry_and_marks_invoice_unpaid(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_input_invoice(tenant)

    created = _create_payment(client, headers, invoice_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    deleted = client.delete(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert deleted.status_code == 204, deleted.text

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is False
        assert db.get(CashEntry, payment_id) is None


def test_delete_payment_is_rejected_for_finalized_payment_month(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-finalized-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_input_invoice(tenant)

    created = _create_payment(
        client,
        headers,
        invoice_id,
        payment_date="2026-08-18",
    )
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    _finalize_month(
        tenant,
        year=2026,
        month=8,
    )

    deleted = client.delete(
        f"/input-invoices/{invoice_id}/payment",
        headers=headers,
    )

    assert deleted.status_code == 400, deleted.text

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True
        assert db.get(CashEntry, payment_id) is not None


def test_direct_cash_delete_cannot_remove_input_invoice_payment(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-cash-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_input_invoice(tenant)

    created = _create_payment(client, headers, invoice_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    deleted = client.delete(
        f"/cash/{payment_id}",
        headers=headers,
    )

    assert deleted.status_code == 409, deleted.text
    assert deleted.json() == {
        "detail": (
            "Input invoice payments must be removed through the "
            "input invoice payment endpoint"
        )
    }

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True
        assert db.get(CashEntry, payment_id) is not None


def test_regular_update_rejects_payment_status_field(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-update-status")
    invoice_id = _create_input_invoice(headers["X-Tenant-Code"])

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={"is_paid": True},
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "extra_forbidden"
        and item["loc"] == ["body", "is_paid"]
        for item in detail
    )

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is False

def test_create_endpoint_rejects_manual_paid_status(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-create-status")
    suffix = uuid4().hex[:10]

    response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"Manual paid supplier {suffix}",
            "invoice_number": f"MANUAL-{suffix}",
            "issue_date": "2026-08-10",
            "posting_date": "2026-08-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
            "is_paid": True,
        },
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "extra_forbidden"
        and item["loc"] == ["body", "is_paid"]
        for item in detail
    )

def test_create_endpoint_rejects_currency_field(
    client: TestClient,
) -> None:
    headers = _headers("input-create-currency")
    suffix = uuid4().hex[:10]

    response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"Currency supplier {suffix}",
            "invoice_number": f"CURRENCY-{suffix}",
            "issue_date": "2026-08-10",
            "posting_date": "2026-08-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
            "currency": "EUR",
        },
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "extra_forbidden"
        and item["loc"] == ["body", "currency"]
        for item in detail
    )

def test_regular_update_rejects_currency_field(
    client: TestClient,
) -> None:
    headers = _headers("input-update-currency")
    invoice_id = _create_input_invoice(headers["X-Tenant-Code"])

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={"currency": "EUR"},
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "extra_forbidden"
        and item["loc"] == ["body", "currency"]
        for item in detail
    )

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.currency == "BAM"

def test_paid_invoice_financial_fields_cannot_be_changed(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-financial-update")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_input_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    created = _create_payment(client, headers, invoice_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "total_base": "200.00",
            "total_vat": "34.00",
            "total_amount": "234.00",
        },
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "Financial fields of a paid input invoice cannot be changed; "
            "remove the payment first"
        )
    }

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True
        assert invoice.total_base == Decimal("100.00")
        assert invoice.total_vat == Decimal("17.00")
        assert invoice.total_amount == Decimal("117.00")

        payment = db.get(CashEntry, payment_id)
        assert payment is not None
        assert payment.amount == Decimal("117.00")
        assert payment.input_invoice_id == invoice_id


def test_paid_invoice_cannot_be_deleted(
    client: TestClient,
) -> None:
    headers = _headers("input-payment-invoice-delete")
    tenant = headers["X-Tenant-Code"]
    invoice_id = _create_input_invoice(tenant)

    created = _create_payment(client, headers, invoice_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    response = client.delete(
        f"/input-invoices/{invoice_id}",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "Input invoice with an existing payment cannot be deleted; "
            "remove the payment first"
        )
    }

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.is_paid is True

        payment = db.get(CashEntry, payment_id)
        assert payment is not None
        assert payment.input_invoice_id == invoice_id


def test_input_invoice_cannot_move_out_of_finalized_issue_month(
    client: TestClient,
) -> None:
    headers = _headers("input-finalized-date-move")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )

    _finalize_month(
        tenant,
        year=2026,
        month=5,
    )

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "issue_date": "2026-06-10",
        },
    )

    assert response.status_code == 400, response.text
    assert (
        "Cannot modify data for finalized tax period 2026-05"
        in response.json()["detail"]
    )

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.issue_date == date(2026, 5, 10)


def test_input_invoice_create_rejects_inconsistent_amounts(
    client: TestClient,
) -> None:
    headers = _headers("input-amount-create")
    tenant = headers["X-Tenant-Code"]
    suffix = uuid4().hex[:10]

    response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"Invalid amount supplier {suffix}",
            "invoice_number": f"INVALID-{suffix}",
            "issue_date": "2026-08-10",
            "posting_date": "2026-08-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "118.00",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": "total_amount must equal total_base + total_vat"
    }

    with SessionLocal() as db:
        invoice = db.execute(
            select(InputInvoice).where(
                InputInvoice.tenant_code == tenant,
                InputInvoice.invoice_number == f"INVALID-{suffix}",
            )
        ).scalar_one_or_none()

        assert invoice is None


def test_input_invoice_partial_update_rejects_inconsistent_amounts(
    client: TestClient,
) -> None:
    headers = _headers("input-amount-update")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "total_amount": "118.00",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": "total_amount must equal total_base + total_vat"
    }

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.total_base == Decimal("100.00")
        assert invoice.total_vat == Decimal("17.00")
        assert invoice.total_amount == Decimal("117.00")

def test_input_invoice_partial_update_rejects_null_amount(
    client: TestClient,
) -> None:
    headers = _headers("input-amount-null")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "total_amount": None,
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": "Input invoice amounts cannot be null"
    }

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.total_base == Decimal("100.00")
        assert invoice.total_vat == Decimal("17.00")
        assert invoice.total_amount == Decimal("117.00")


def test_input_invoice_create_rejects_zero_total_amount(
    client: TestClient,
) -> None:
    headers = _headers("input-zero-total-create")
    suffix = uuid4().hex[:10]

    response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"Zero total supplier {suffix}",
            "invoice_number": f"ZERO-{suffix}",
            "issue_date": "2026-08-10",
            "posting_date": "2026-08-10",
            "total_base": "0.00",
            "total_vat": "0.00",
            "total_amount": "0.00",
        },
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "greater_than"
        and item["loc"] == ["body", "total_amount"]
        for item in detail
    )


def test_input_invoice_update_rejects_zero_total_amount(
    client: TestClient,
) -> None:
    headers = _headers("input-zero-total-update")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "total_amount": "0.00",
        },
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "greater_than"
        and item["loc"] == ["body", "total_amount"]
        for item in detail
    )

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.total_amount == Decimal("117.00")



def test_input_invoice_create_trims_supplier_name_and_invoice_number(
    client: TestClient,
) -> None:
    headers = _headers("input-trim-create")
    suffix = uuid4().hex[:10]

    supplier_name = f"Trim supplier {suffix}"
    invoice_number = f"TRIM-{suffix}"

    response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"  {supplier_name}  ",
            "invoice_number": f"  {invoice_number}  ",
            "issue_date": "2026-08-10",
            "posting_date": "2026-08-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["supplier_name"] == supplier_name
    assert data["invoice_number"] == invoice_number


@pytest.mark.parametrize(
    "field_name",
    ["supplier_name", "invoice_number"],
)
def test_input_invoice_create_rejects_whitespace_only_required_text(
    client: TestClient,
    field_name: str,
) -> None:
    headers = _headers(f"input-whitespace-{field_name}")
    suffix = uuid4().hex[:10]

    payload = {
        "supplier_name": f"Whitespace supplier {suffix}",
        "invoice_number": f"WS-{suffix}",
        "issue_date": "2026-08-10",
        "posting_date": "2026-08-10",
        "total_base": "100.00",
        "total_vat": "17.00",
        "total_amount": "117.00",
    }
    payload[field_name] = "   "

    response = client.post(
        "/input-invoices",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "string_too_short"
        and item["loc"] == ["body", field_name]
        for item in detail
    )


def test_input_invoice_update_trims_supplier_name_and_invoice_number(
    client: TestClient,
) -> None:
    headers = _headers("input-trim-update")
    tenant = headers["X-Tenant-Code"]
    suffix = uuid4().hex[:10]

    invoice_id = _create_input_invoice(tenant)

    supplier_name = f"Updated supplier {suffix}"
    invoice_number = f"UPDATED-{suffix}"

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "supplier_name": f"  {supplier_name}  ",
            "invoice_number": f"  {invoice_number}  ",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["supplier_name"] == supplier_name
    assert data["invoice_number"] == invoice_number

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.supplier_name == supplier_name
        assert invoice.invoice_number == invoice_number

@pytest.mark.parametrize(
    "field_name",
    ["supplier_name", "invoice_number"],
)
def test_input_invoice_update_rejects_whitespace_only_required_text(
    client: TestClient,
    field_name: str,
) -> None:
    headers = _headers(f"input-update-whitespace-{field_name}")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(tenant)

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            field_name: "   ",
        },
    )

    assert response.status_code == 422, response.text

    detail = response.json()["detail"]
    assert any(
        item["type"] == "string_too_short"
        and item["loc"] == ["body", field_name]
        for item in detail
    )


def test_input_invoice_create_rejects_due_date_before_issue_date(
    client: TestClient,
) -> None:
    headers = _headers("input-invalid-due-create")
    suffix = uuid4().hex[:10]

    response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"Invalid due supplier {suffix}",
            "invoice_number": f"DUE-{suffix}",
            "issue_date": "2026-08-10",
            "due_date": "2026-08-09",
            "posting_date": "2026-08-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": "due_date cannot be before issue_date"
    }


def test_input_invoice_update_rejects_due_date_before_existing_issue_date(
    client: TestClient,
) -> None:
    headers = _headers("input-invalid-due-update")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "due_date": "2026-05-09",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": "due_date cannot be before issue_date"
    }


def test_input_invoice_update_rejects_issue_date_after_existing_due_date(
    client: TestClient,
) -> None:
    headers = _headers("input-invalid-issue-update")
    suffix = uuid4().hex[:10]

    created = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": f"Date relation supplier {suffix}",
            "invoice_number": f"DATE-{suffix}",
            "issue_date": "2026-08-10",
            "due_date": "2026-08-15",
            "posting_date": "2026-08-10",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert created.status_code == 201, created.text

    invoice_id = created.json()["id"]

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            "issue_date": "2026-08-16",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": "due_date cannot be before issue_date"
    }


@pytest.mark.parametrize(
    ("field_name", "expected_detail"),
    [
        ("supplier_name", "Input invoice required fields cannot be null"),
        ("invoice_number", "Input invoice required fields cannot be null"),
        ("issue_date", "Input invoice required fields cannot be null"),
        ("is_tax_deductible", "Input invoice required fields cannot be null"),
        ("total_base", "Input invoice amounts cannot be null"),
        ("total_vat", "Input invoice amounts cannot be null"),
    ],
)
def test_input_invoice_update_rejects_null_not_nullable_fields(
    client: TestClient,
    field_name: str,
    expected_detail: str,
) -> None:
    headers = _headers(f"input-null-{field_name}")
    tenant = headers["X-Tenant-Code"]

    invoice_id = _create_input_invoice(
        tenant,
        total_amount=Decimal("117.00"),
    )

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=headers,
        json={
            field_name: None,
        },
    )

    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": expected_detail
    }

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        assert invoice is not None
        assert invoice.supplier_name is not None
        assert invoice.invoice_number is not None
        assert invoice.issue_date is not None
        assert invoice.is_tax_deductible is not None
        assert invoice.total_base == Decimal("100.00")
        assert invoice.total_vat == Decimal("17.00")
        assert invoice.total_amount == Decimal("117.00")
