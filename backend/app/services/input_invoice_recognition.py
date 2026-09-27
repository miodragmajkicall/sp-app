from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashEntry, InputInvoice
from app.services.tax_recognition import (
    RecognitionBasis,
    RecognitionStatus,
    TenantRecognitionContext,
    resolve_tenant_recognition_context,
)


@dataclass(frozen=True)
class InputInvoiceRecognition:
    basis: RecognitionBasis
    status: RecognitionStatus
    recognition_date: date | None
    integrity_date: date | None


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
    # Za plaćenu fakturu poreski recognition događaj nastaje na payment_date,
    # pa profil mora biti onaj koji je važio baš tog dana.
    # Za neplaćenu fakturu recognition događaj još ne postoji; current profil
    # služi samo za trenutni status/basis.
    context = resolve_tenant_recognition_context(
        db,
        invoice.tenant_code,
        as_of=payment_date,
    )
    return resolve_input_invoice_recognition(
        context=context,
        payment_date=payment_date,
    )
