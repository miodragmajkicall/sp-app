from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CashEntry, Invoice
from app.services.output_invoice_recognition import (
    resolve_output_invoice_recognition,
)
from app.services.tax_recognition import (
    RecognitionBasis,
    RecognitionStatus,
    resolve_tenant_recognition_context,
)


class UnsupportedOutputIncomeRecognitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecognizedOutputIncome:
    invoice_id: int
    recognition_date: date
    amount: Decimal
    buyer_name: str
    invoice_number: str
    note: str | None


def list_recognized_output_income(
    db: Session,
    *,
    tenant_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    month: int | None = None,
) -> list[RecognizedOutputIncome]:
    """Return tenant-owned output invoice income recognized in the period.

    Output invoices are documentary records. Under CASH recognition they enter
    the recognized dataset only through their linked payment CashEntry and are
    dated by CashEntry.entry_date. Unsupported recognition context never falls
    back to Invoice.issue_date.
    """
    filters = [
        Invoice.tenant_code == tenant_code,
        CashEntry.tenant_code == tenant_code,
        CashEntry.invoice_id == Invoice.id,
    ]

    if date_from is not None:
        filters.append(CashEntry.entry_date >= date_from)

    if date_to is not None:
        filters.append(CashEntry.entry_date < date_to)

    if month is not None:
        filters.append(func.extract("month", CashEntry.entry_date) == month)

    stmt = (
        select(Invoice, CashEntry.entry_date)
        .join(CashEntry, CashEntry.invoice_id == Invoice.id)
        .where(*filters)
        .order_by(CashEntry.entry_date.asc(), Invoice.id.asc())
    )

    rows = db.execute(stmt).all()
    if not rows:
        return []

    contexts = {}
    recognized: list[RecognizedOutputIncome] = []

    for invoice, payment_date in rows:
        if payment_date not in contexts:
            contexts[payment_date] = resolve_tenant_recognition_context(
                db,
                tenant_code,
                as_of=payment_date,
            )

        context = contexts[payment_date]

        if context.basis is not RecognitionBasis.CASH:
            raise UnsupportedOutputIncomeRecognitionError(
                "Output invoice recognition policy is not configured for this tenant"
            )

        recognition = resolve_output_invoice_recognition(
            context=context,
            payment_date=payment_date,
        )

        if (
            recognition.status is not RecognitionStatus.RECOGNIZED
            or recognition.recognition_date is None
        ):
            continue

        recognized.append(
            RecognizedOutputIncome(
                invoice_id=invoice.id,
                recognition_date=recognition.recognition_date,
                amount=Decimal(str(invoice.total_amount)),
                buyer_name=invoice.buyer_name,
                invoice_number=invoice.invoice_number,
                note=invoice.note,
            )
        )

    return recognized
