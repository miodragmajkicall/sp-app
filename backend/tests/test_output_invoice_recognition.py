from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db import SessionLocal
from app.models import CashEntry, Invoice, TenantTaxProfileSettings
from app.services import output_invoice_recognition as recognition_service
from app.services.output_invoice_recognition import (
    resolve_output_invoice_recognition,
    resolve_stored_output_invoice_recognition,
)
from app.services.recognized_output_income import (
    UnsupportedOutputIncomeRecognitionError,
    list_recognized_output_income,
)
from app.services.tax_recognition import (
    RecognitionBasis,
    RecognitionStatus,
    TenantRecognitionContext,
)
from app.tenant_security import ensure_tenant_exists


def _tenant(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _add_profile(
    db,
    tenant: str,
    *,
    regime: str = "pausal",
    effective_from: date = date(2026, 1, 1),
) -> None:
    ensure_tenant_exists(db, tenant)
    db.add(
        TenantTaxProfileSettings(
            tenant_code=tenant,
            entity="RS",
            regime=regime,
            scenario_key="rs_primary",
            has_additional_activity=False,
            effective_from=effective_from,
        )
    )


def _add_invoice(
    db,
    tenant: str,
    *,
    issue_date: date = date(2026, 5, 10),
    total_amount: Decimal = Decimal("117.00"),
) -> Invoice:
    ensure_tenant_exists(db, tenant)

    suffix = uuid4().hex[:10]
    invoice = Invoice(
        tenant_code=tenant,
        invoice_number=f"OUT-REC-{suffix}",
        issue_date=issue_date,
        buyer_name=f"Recognition buyer {suffix}",
        total_base=Decimal("100.00"),
        total_vat=total_amount - Decimal("100.00"),
        total_amount=total_amount,
        is_paid=False,
    )
    db.add(invoice)
    db.flush()
    return invoice


def _add_payment(
    db,
    tenant: str,
    invoice: Invoice,
    *,
    payment_date: date,
) -> CashEntry:
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
    )
    db.add(payment)
    invoice.is_paid = True
    db.flush()
    return payment


def test_output_invoice_recognition_cash_contract() -> None:
    context = TenantRecognitionContext(
        basis=RecognitionBasis.CASH,
        jurisdiction="RS",
        regime="pausal",
        scenario_key="rs_primary",
    )

    unpaid = resolve_output_invoice_recognition(
        context=context,
        payment_date=None,
    )

    assert unpaid.basis is RecognitionBasis.CASH
    assert unpaid.status is RecognitionStatus.NOT_RECOGNIZED
    assert unpaid.recognition_date is None
    assert unpaid.integrity_date is None

    paid = resolve_output_invoice_recognition(
        context=context,
        payment_date=date(2026, 8, 18),
    )

    assert paid.basis is RecognitionBasis.CASH
    assert paid.status is RecognitionStatus.RECOGNIZED
    assert paid.recognition_date == date(2026, 8, 18)
    assert paid.integrity_date == date(2026, 8, 18)


def test_output_invoice_recognition_unresolved_fails_closed() -> None:
    context = TenantRecognitionContext(
        basis=RecognitionBasis.UNRESOLVED,
        jurisdiction="RS",
        regime="books",
        scenario_key="rs_primary",
    )

    result = resolve_output_invoice_recognition(
        context=context,
        payment_date=date(2026, 8, 18),
    )

    assert result.basis is RecognitionBasis.UNRESOLVED
    assert result.status is RecognitionStatus.UNSUPPORTED
    assert result.recognition_date is None
    assert result.integrity_date == date(2026, 8, 18)


def test_stored_output_recognition_anchors_context_to_payment_date(
    monkeypatch,
) -> None:
    payment_date = date(2026, 8, 18)
    captured: dict[str, object] = {}

    class ScalarResult:
        def scalar_one_or_none(self):
            return payment_date

    class FakeSession:
        def execute(self, statement):
            return ScalarResult()

    def fake_context(
        db,
        tenant_code,
        *,
        as_of=None,
    ):
        captured["tenant_code"] = tenant_code
        captured["as_of"] = as_of
        return TenantRecognitionContext(
            basis=RecognitionBasis.CASH,
            jurisdiction="RS",
            regime="pausal",
            scenario_key="rs_primary",
        )

    monkeypatch.setattr(
        recognition_service,
        "resolve_tenant_recognition_context",
        fake_context,
    )

    invoice = SimpleNamespace(
        id=123,
        tenant_code="output-recognition-payment-date",
    )

    result = resolve_stored_output_invoice_recognition(
        FakeSession(),
        invoice,
    )

    assert captured["tenant_code"] == "output-recognition-payment-date"
    assert captured["as_of"] == payment_date
    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.recognition_date == payment_date
    assert result.integrity_date == payment_date


def test_recognized_output_income_uses_payment_period_not_issue_period() -> None:
    tenant = _tenant("output-period")

    with SessionLocal() as db:
        _add_profile(db, tenant)

        invoice = _add_invoice(
            db,
            tenant,
            issue_date=date(2026, 5, 10),
        )
        _add_payment(
            db,
            tenant,
            invoice,
            payment_date=date(2026, 8, 18),
        )
        db.commit()

        may_rows = list_recognized_output_income(
            db,
            tenant_code=tenant,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 6, 1),
        )
        august_rows = list_recognized_output_income(
            db,
            tenant_code=tenant,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 9, 1),
        )

        assert may_rows == []
        assert len(august_rows) == 1

        row = august_rows[0]
        assert row.invoice_id == invoice.id
        assert row.recognition_date == date(2026, 8, 18)
        assert row.amount == Decimal("117.00")
        assert row.invoice_number == invoice.invoice_number
        assert row.buyer_name == invoice.buyer_name


def test_unpaid_output_invoice_is_not_recognized() -> None:
    tenant = _tenant("output-unpaid")

    with SessionLocal() as db:
        _add_profile(db, tenant)
        _add_invoice(db, tenant)
        db.commit()

        assert list_recognized_output_income(
            db,
            tenant_code=tenant,
        ) == []


def test_recognized_output_income_is_tenant_isolated() -> None:
    owner = _tenant("output-owner")
    other = _tenant("output-other")

    with SessionLocal() as db:
        _add_profile(db, owner)
        _add_profile(db, other)

        invoice = _add_invoice(db, owner)
        _add_payment(
            db,
            owner,
            invoice,
            payment_date=date(2026, 8, 18),
        )
        db.commit()

        assert len(
            list_recognized_output_income(
                db,
                tenant_code=owner,
            )
        ) == 1

        assert list_recognized_output_income(
            db,
            tenant_code=other,
        ) == []


def test_recognized_output_income_fails_closed_for_unsupported_context() -> None:
    tenant = _tenant("output-unsupported")

    with SessionLocal() as db:
        _add_profile(
            db,
            tenant,
            regime="books",
        )

        invoice = _add_invoice(db, tenant)
        _add_payment(
            db,
            tenant,
            invoice,
            payment_date=date(2026, 8, 18),
        )
        db.commit()

        with pytest.raises(
            UnsupportedOutputIncomeRecognitionError,
            match="Output invoice recognition policy is not configured",
        ):
            list_recognized_output_income(
                db,
                tenant_code=tenant,
            )


def test_unsupported_context_without_payment_in_period_returns_empty() -> None:
    tenant = _tenant("output-empty-period")

    with SessionLocal() as db:
        _add_profile(
            db,
            tenant,
            regime="books",
        )

        invoice = _add_invoice(db, tenant)
        _add_payment(
            db,
            tenant,
            invoice,
            payment_date=date(2026, 6, 30),
        )
        db.commit()

        assert list_recognized_output_income(
            db,
            tenant_code=tenant,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 8, 1),
        ) == []
