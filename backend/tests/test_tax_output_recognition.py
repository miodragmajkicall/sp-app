from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import CashEntry, Invoice
from app.tenant_security import ensure_tenant_exists
from tests.tax_config_helpers import set_strict_tax_test_context


client = TestClient(app)


def _headers(prefix: str) -> dict[str, str]:
    return {"X-Tenant-Code": f"{prefix}-{uuid4().hex[:10]}"}


def _create_invoice(
    tenant: str,
    *,
    issue_date: date,
    amount: Decimal = Decimal("117.00"),
) -> int:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant)

        invoice = Invoice(
            tenant_code=tenant,
            invoice_number=f"TAX-OUT-{uuid4().hex[:10]}",
            issue_date=issue_date,
            buyer_name="TAX output recognition buyer",
            total_base=Decimal("100.00"),
            total_vat=amount - Decimal("100.00"),
            total_amount=amount,
            is_paid=False,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice.id


def _pay_invoice(
    tenant: str,
    invoice_id: int,
    *,
    payment_date: date,
) -> None:
    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None

        db.add(
            CashEntry(
                tenant_code=tenant,
                entry_date=payment_date,
                kind="income",
                amount=invoice.total_amount,
                account="bank",
                recognition_class=None,
                tax_treatment=None,
                invoice_id=invoice.id,
                input_invoice_id=None,
            )
        )
        invoice.is_paid = True
        db.commit()


def test_tax_output_invoice_uses_payment_period_not_issue_period() -> None:
    headers = _headers("tax-output-cross-period")
    tenant = headers["X-Tenant-Code"]

    set_strict_tax_test_context(
        client,
        headers,
        effective_from="2026-01-01",
    )

    invoice_id = _create_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )
    _pay_invoice(
        tenant,
        invoice_id,
        payment_date=date(2026, 8, 18),
    )

    may = client.get(
        "/tax/monthly/auto",
        params={"year": 2026, "month": 5},
        headers=headers,
    )
    assert may.status_code == 200, may.text
    assert Decimal(str(may.json()["total_income"])) == Decimal("0.00")

    august = client.get(
        "/tax/monthly/auto",
        params={"year": 2026, "month": 8},
        headers=headers,
    )
    assert august.status_code == 200, august.text
    assert Decimal(str(august.json()["total_income"])) == Decimal("117.00")


def test_tax_unpaid_output_invoice_is_not_recognized() -> None:
    headers = _headers("tax-output-unpaid")
    tenant = headers["X-Tenant-Code"]

    set_strict_tax_test_context(
        client,
        headers,
        effective_from="2026-01-01",
    )

    _create_invoice(
        tenant,
        issue_date=date(2026, 8, 10),
    )

    response = client.get(
        "/tax/monthly/auto",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_income"])) == Decimal("0.00")


def test_tax_output_payment_is_not_double_counted_with_manual_cash() -> None:
    headers = _headers("tax-output-no-double")
    tenant = headers["X-Tenant-Code"]

    set_strict_tax_test_context(
        client,
        headers,
        effective_from="2026-01-01",
    )

    invoice_id = _create_invoice(
        tenant,
        issue_date=date(2026, 8, 10),
    )
    _pay_invoice(
        tenant,
        invoice_id,
        payment_date=date(2026, 8, 18),
    )

    with SessionLocal() as db:
        db.add(
            CashEntry(
                tenant_code=tenant,
                entry_date=date(2026, 8, 20),
                kind="income",
                amount=Decimal("50.00"),
                account="cash",
                recognition_class="business_activity",
                tax_treatment=None,
                invoice_id=None,
                input_invoice_id=None,
                description="Independent manual income",
            )
        )
        db.commit()

    response = client.get(
        "/tax/monthly/auto",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_income"])) == Decimal("167.00")


def test_tax_output_recognition_fails_closed_for_unsupported_context() -> None:
    headers = _headers("tax-output-unsupported")
    tenant = headers["X-Tenant-Code"]

    set_strict_tax_test_context(
        client,
        headers,
        regime="books",
        scenario_key="rs_primary",
        has_additional_activity=False,
        effective_from="2026-01-01",
    )

    invoice_id = _create_invoice(
        tenant,
        issue_date=date(2026, 8, 10),
    )
    _pay_invoice(
        tenant,
        invoice_id,
        payment_date=date(2026, 8, 18),
    )

    response = client.get(
        "/tax/monthly/auto",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert (
        "Output invoice recognition policy is not configured"
        in response.json()["detail"]
    )
