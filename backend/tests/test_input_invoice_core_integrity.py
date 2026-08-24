from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    CashEntry,
    InputInvoice,
    TaxMonthlyResult,
    TenantTaxProfileSettings,
)
from app.services.input_invoice_recognition import (
    RecognitionBasis,
    RecognitionStatus,
    TenantRecognitionContext,
    resolve_input_invoice_recognition,
    resolve_stored_input_invoice_recognition,
)
from app.tenant_security import ensure_tenant_exists


client = TestClient(app)


def _tenant(prefix: str) -> str:
    return f"{uuid4().hex[:10]}-{prefix}"


def _headers(tenant: str) -> dict[str, str]:
    return {"X-Tenant-Code": tenant}


def _create_invoice(tenant: str, issue_date: str = "2026-05-10") -> int:
    suffix = uuid4().hex[:10]
    response = client.post(
        "/input-invoices",
        headers=_headers(tenant),
        json={
            "supplier_name": f"Core supplier {suffix}",
            "invoice_number": f"CORE-{suffix}",
            "issue_date": issue_date,
            "posting_date": issue_date,
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


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


def _finalize(tenant: str, year: int, month: int) -> None:
    with SessionLocal() as db:
        db.add(
            TaxMonthlyResult(
                tenant_code=tenant,
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


def _pay(tenant: str, invoice_id: int, payment_date: str = "2026-08-18"):
    return client.post(
        f"/input-invoices/{invoice_id}/payment",
        headers=_headers(tenant),
        json={"payment_date": payment_date, "account": "bank"},
    )


def test_cash_basis_resolver_is_explicit_for_unpaid_and_paid() -> None:
    context = TenantRecognitionContext(
        basis=RecognitionBasis.CASH,
        jurisdiction="RS",
        regime="pausal",
        scenario_key="rs_primary",
    )

    unpaid = resolve_input_invoice_recognition(context=context, payment_date=None)
    assert unpaid.status is RecognitionStatus.NOT_RECOGNIZED
    assert unpaid.recognition_date is None
    assert unpaid.integrity_date is None

    paid = resolve_input_invoice_recognition(
        context=context,
        payment_date=date(2026, 8, 18),
    )
    assert paid.status is RecognitionStatus.RECOGNIZED
    assert paid.recognition_date == date(2026, 8, 18)
    assert paid.integrity_date == date(2026, 8, 18)


def test_unsupported_context_does_not_claim_recognition_but_is_fail_safe() -> None:
    unresolved = TenantRecognitionContext(
        basis=RecognitionBasis.UNRESOLVED,
        jurisdiction=None,
        regime=None,
        scenario_key=None,
    )
    result = resolve_input_invoice_recognition(
        context=unresolved,
        payment_date=date(2026, 8, 18),
    )

    assert result.status is RecognitionStatus.UNSUPPORTED
    assert result.recognition_date is None
    assert result.integrity_date == date(2026, 8, 18)


def test_unpaid_create_does_not_use_finalized_issue_month_as_recognition() -> None:
    tenant = _tenant("core-create")
    _set_cash_profile(tenant)
    _finalize(tenant, 2026, 5)

    invoice_id = _create_invoice(tenant, "2026-05-10")

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        result = resolve_stored_input_invoice_recognition(db, invoice)
        assert result.status is RecognitionStatus.NOT_RECOGNIZED
        assert result.recognition_date is None


def test_posting_only_change_has_no_unpaid_recognition_period() -> None:
    tenant = _tenant("core-posting")
    _set_cash_profile(tenant)
    invoice_id = _create_invoice(tenant)
    _finalize(tenant, 2026, 5)

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=_headers(tenant),
        json={"posting_date": "2026-06-01"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["posting_date"] == "2026-06-01"


def test_issue_date_change_keeps_payment_based_recognition_period() -> None:
    tenant = _tenant("core-issue")
    _set_cash_profile(tenant)
    invoice_id = _create_invoice(tenant)
    assert _pay(tenant, invoice_id).status_code == 201

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=_headers(tenant),
        json={"issue_date": "2026-06-10"},
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        result = resolve_stored_input_invoice_recognition(db, invoice)
        assert result.recognition_date == date(2026, 8, 18)


def test_paid_tax_sensitive_change_checks_finalized_payment_period() -> None:
    tenant = _tenant("core-paid-lock")
    _set_cash_profile(tenant)
    invoice_id = _create_invoice(tenant)
    assert _pay(tenant, invoice_id).status_code == 201
    _finalize(tenant, 2026, 8)

    response = client.put(
        f"/input-invoices/{invoice_id}",
        headers=_headers(tenant),
        json={"is_tax_deductible": False},
    )
    assert response.status_code == 400, response.text
    assert "finalized tax period 2026-08" in response.json()["detail"]


def test_resolver_payment_lookup_is_tenant_constrained() -> None:
    owner = _tenant("core-owner")
    other = _tenant("core-other")
    _set_cash_profile(owner)
    _set_cash_profile(other)
    invoice_id = _create_invoice(owner)
    assert _pay(owner, invoice_id).status_code == 201

    with SessionLocal() as db:
        invoice = db.get(InputInvoice, invoice_id)
        result = resolve_stored_input_invoice_recognition(db, invoice)
        payment = db.execute(
            select(CashEntry).where(
                CashEntry.tenant_code == owner,
                CashEntry.input_invoice_id == invoice_id,
            )
        ).scalar_one()
        assert result.recognition_date == payment.entry_date
        assert result.recognition_date == date(2026, 8, 18)

    foreign = client.get(
        f"/input-invoices/{invoice_id}",
        headers=_headers(other),
    )
    assert foreign.status_code == 404
