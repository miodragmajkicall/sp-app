from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashEntry, InputInvoice, TenantTaxProfileSettings


class RecognitionBasis(str, Enum):
    CASH = "cash"
    UNRESOLVED = "unresolved"


class RecognitionStatus(str, Enum):
    RECOGNIZED = "recognized"
    NOT_RECOGNIZED = "not_recognized"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class TenantRecognitionContext:
    basis: RecognitionBasis
    jurisdiction: str | None
    regime: str | None
    scenario_key: str | None


@dataclass(frozen=True)
class InputInvoiceRecognition:
    basis: RecognitionBasis
    status: RecognitionStatus
    recognition_date: date | None
    integrity_date: date | None


_SUPPORTED_ENTITIES = {"RS", "FBIH", "BD", "BRCKO", "BRČKO"}
_CASH_BASIS_REGIMES = {"pausal", "two_percent"}


def resolve_tenant_recognition_context(
    db: Session,
    tenant_code: str,
) -> TenantRecognitionContext:
    profile = db.execute(
        select(TenantTaxProfileSettings).where(
            TenantTaxProfileSettings.tenant_code == tenant_code
        )
    ).scalar_one_or_none()

    if profile is None:
        return TenantRecognitionContext(RecognitionBasis.UNRESOLVED, None, None, None)

    entity = (profile.entity or "").strip().upper()
    regime = (profile.regime or "").strip().lower()
    scenario_key = (profile.scenario_key or "").strip() or None
    basis = (
        RecognitionBasis.CASH
        if entity in _SUPPORTED_ENTITIES and regime in _CASH_BASIS_REGIMES
        else RecognitionBasis.UNRESOLVED
    )
    return TenantRecognitionContext(basis, entity or None, regime or None, scenario_key)


def resolve_input_invoice_recognition(
    *,
    context: TenantRecognitionContext,
    payment_date: date | None,
) -> InputInvoiceRecognition:
    if context.basis is RecognitionBasis.CASH:
        if payment_date is None:
            return InputInvoiceRecognition(
                basis=context.basis,
                status=RecognitionStatus.NOT_RECOGNIZED,
                recognition_date=None,
                integrity_date=None,
            )
        return InputInvoiceRecognition(
            basis=context.basis,
            status=RecognitionStatus.RECOGNIZED,
            recognition_date=payment_date,
            integrity_date=payment_date,
        )

    # Do not claim tax recognition for an unsupported context.  If a payment
    # exists, its month is retained only as a fail-safe finalized-period guard.
    return InputInvoiceRecognition(
        basis=RecognitionBasis.UNRESOLVED,
        status=RecognitionStatus.UNSUPPORTED,
        recognition_date=None,
        integrity_date=payment_date,
    )


def resolve_stored_input_invoice_recognition(
    db: Session,
    invoice: InputInvoice,
) -> InputInvoiceRecognition:
    payment_date = db.execute(
        select(CashEntry.entry_date).where(
            CashEntry.tenant_code == invoice.tenant_code,
            CashEntry.input_invoice_id == invoice.id,
        )
    ).scalar_one_or_none()
    context = resolve_tenant_recognition_context(db, invoice.tenant_code)
    return resolve_input_invoice_recognition(
        context=context,
        payment_date=payment_date,
    )
