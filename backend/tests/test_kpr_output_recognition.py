from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import CashEntry, Invoice, TenantTaxProfileSettings
from app.tenant_security import ensure_tenant_exists


client = TestClient(app)


def _headers(prefix: str) -> dict[str, str]:
    return {"X-Tenant-Code": f"{prefix}-{uuid4().hex[:10]}"}


def _add_profile(
    tenant: str,
    *,
    regime: str = "pausal",
) -> None:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant)
        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant,
                entity="RS",
                regime=regime,
                scenario_key="rs_primary",
                has_additional_activity=False,
                effective_from=date(2026, 1, 1),
            )
        )
        db.commit()


def _add_invoice(
    tenant: str,
    *,
    issue_date: date,
    amount: Decimal = Decimal("117.00"),
) -> int:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant)

        suffix = uuid4().hex[:10]
        invoice = Invoice(
            tenant_code=tenant,
            invoice_number=f"KPR-OUT-{suffix}",
            issue_date=issue_date,
            buyer_name=f"KPR output buyer {suffix}",
            total_base=Decimal("100.00"),
            total_vat=amount - Decimal("100.00"),
            total_amount=amount,
            is_paid=False,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice.id


def _add_payment(
    tenant: str,
    invoice_id: int,
    *,
    payment_date: date,
) -> int:
    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None

        payment = CashEntry(
            tenant_code=tenant,
            entry_date=payment_date,
            kind="income",
            amount=invoice.total_amount,
            account="bank",
            recognition_class=None,
            tax_treatment=None,
            invoice_id=invoice.id,
            input_invoice_id=None,
            description="KPR canonical output payment",
        )
        db.add(payment)
        invoice.is_paid = True
        db.commit()
        db.refresh(payment)
        return payment.id


def test_kpr_output_invoice_uses_payment_period_not_issue_period() -> None:
    headers = _headers("kpr-output-period")
    tenant = headers["X-Tenant-Code"]

    _add_profile(tenant)

    invoice_id = _add_invoice(
        tenant,
        issue_date=date(2026, 5, 10),
    )
    _add_payment(
        tenant,
        invoice_id,
        payment_date=date(2026, 8, 18),
    )

    may = client.get(
        "/kpr",
        params={"year": 2026, "month": 5},
        headers=headers,
    )
    assert may.status_code == 200, may.text
    assert not any(
        row["source"] == "invoice"
        and row["source_id"] == invoice_id
        for row in may.json()["items"]
    )

    august = client.get(
        "/kpr",
        params={"year": 2026, "month": 8},
        headers=headers,
    )
    assert august.status_code == 200, august.text

    rows = [
        row
        for row in august.json()["items"]
        if row["source"] == "invoice"
        and row["source_id"] == invoice_id
    ]

    assert len(rows) == 1
    assert rows[0]["date"] == "2026-08-18"
    assert Decimal(str(rows[0]["amount"])) == Decimal("117.00")


def test_kpr_unpaid_output_invoice_is_not_recognized() -> None:
    headers = _headers("kpr-output-unpaid")
    tenant = headers["X-Tenant-Code"]

    _add_profile(tenant)

    invoice_id = _add_invoice(
        tenant,
        issue_date=date(2026, 8, 10),
    )

    response = client.get(
        "/kpr",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert not any(
        row["source"] == "invoice"
        and row["source_id"] == invoice_id
        for row in response.json()["items"]
    )


def test_kpr_output_payment_is_not_double_counted_as_cash() -> None:
    headers = _headers("kpr-output-no-double")
    tenant = headers["X-Tenant-Code"]

    _add_profile(tenant)

    invoice_id = _add_invoice(
        tenant,
        issue_date=date(2026, 8, 10),
    )
    payment_id = _add_payment(
        tenant,
        invoice_id,
        payment_date=date(2026, 8, 18),
    )

    response = client.get(
        "/kpr",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]

    assert sum(
        1
        for row in items
        if row["source"] == "invoice"
        and row["source_id"] == invoice_id
    ) == 1

    assert not any(
        row["source"] == "cash"
        and row["source_id"] == payment_id
        for row in items
    )


def test_kpr_output_recognition_fails_closed_for_unsupported_context() -> None:
    headers = _headers("kpr-output-unsupported")
    tenant = headers["X-Tenant-Code"]

    _add_profile(
        tenant,
        regime="books",
    )

    invoice_id = _add_invoice(
        tenant,
        issue_date=date(2026, 8, 10),
    )
    _add_payment(
        tenant,
        invoice_id,
        payment_date=date(2026, 8, 18),
    )

    response = client.get(
        "/kpr",
        params={"year": 2026, "month": 8},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert (
        "Output invoice recognition policy is not configured"
        in response.json()["detail"]
    )
