from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashEntry, Invoice
from app.services.tax_recognition import (
    RecognitionBasis,
    RecognitionStatus,
    TenantRecognitionContext,
    resolve_tenant_recognition_context,
)


@dataclass(frozen=True)
class OutputInvoiceRecognition:
    basis: RecognitionBasis
    status: RecognitionStatus
    recognition_date: date | None
    integrity_date: date | None


def resolve_output_invoice_recognition(
    *,
    context: TenantRecognitionContext,
    payment_date: date | None,
) -> OutputInvoiceRecognition:
    if context.basis is RecognitionBasis.CASH:
        if payment_date is None:
            return OutputInvoiceRecognition(
                basis=context.basis,
                status=RecognitionStatus.NOT_RECOGNIZED,
                recognition_date=None,
                integrity_date=None,
            )

        return OutputInvoiceRecognition(
            basis=context.basis,
            status=RecognitionStatus.RECOGNIZED,
            recognition_date=payment_date,
            integrity_date=payment_date,
        )

    # Unsupported recognition contexts never fall back to issue_date.
    # A linked payment date is retained only for integrity/finalized-period
    # protection; it does not imply tax recognition.
    return OutputInvoiceRecognition(
        basis=RecognitionBasis.UNRESOLVED,
        status=RecognitionStatus.UNSUPPORTED,
        recognition_date=None,
        integrity_date=payment_date,
    )


def resolve_stored_output_invoice_recognition(
    db: Session,
    invoice: Invoice,
) -> OutputInvoiceRecognition:
    payment_date = db.execute(
        select(CashEntry.entry_date).where(
            CashEntry.tenant_code == invoice.tenant_code,
            CashEntry.invoice_id == invoice.id,
        )
    ).scalar_one_or_none()

    # For a paid invoice the recognition event occurs on payment_date, so
    # recognition policy must be resolved from the profile valid on that date.
    # An unpaid invoice has no recognition event yet; the current profile is
    # used only to describe its current recognition state.
    context = resolve_tenant_recognition_context(
        db,
        invoice.tenant_code,
        as_of=payment_date,
    )

    return resolve_output_invoice_recognition(
        context=context,
        payment_date=payment_date,
    )
