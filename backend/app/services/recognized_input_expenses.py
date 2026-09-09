from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CashEntry, InputInvoice
from app.services.input_invoice_recognition import (
    RecognitionBasis,
    RecognitionStatus,
    resolve_input_invoice_recognition,
    resolve_tenant_recognition_context,
)


class UnsupportedInputExpenseRecognitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecognizedInputExpense:
    invoice_id: int
    recognition_date: date
    amount: Decimal
    is_tax_deductible: bool
    supplier_name: str
    invoice_number: str
    note: str | None
    currency: str


def list_recognized_input_expenses(
    db: Session,
    *,
    tenant_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    month: int | None = None,
) -> list[RecognizedInputExpense]:
    """Return tenant-owned input expenses recognized in the requested period.

    An unsupported recognition context never falls back to issue_date. If paid
    input invoices exist in the requested period, fail closed instead of
    silently producing an incomplete KPR/TAX result.
    """
    filters = [
        InputInvoice.tenant_code == tenant_code,
        CashEntry.tenant_code == tenant_code,
        CashEntry.input_invoice_id == InputInvoice.id,
    ]
    if date_from is not None:
        filters.append(CashEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(CashEntry.entry_date < date_to)
    if month is not None:
        filters.append(func.extract("month", CashEntry.entry_date) == month)

    stmt = (
        select(InputInvoice, CashEntry.entry_date)
        .join(CashEntry, CashEntry.input_invoice_id == InputInvoice.id)
        .where(*filters)
        .order_by(CashEntry.entry_date.asc(), InputInvoice.id.asc())
    )

    rows = db.execute(stmt).all()
    if not rows:
        return []

    context = resolve_tenant_recognition_context(db, tenant_code)
    if context.basis is not RecognitionBasis.CASH:
        raise UnsupportedInputExpenseRecognitionError(
            "Input invoice recognition policy is not configured for this tenant"
        )

    expenses: list[RecognizedInputExpense] = []
    for invoice, payment_date in rows:
        recognition = resolve_input_invoice_recognition(
            context=context,
            payment_date=payment_date,
        )
        if (
            recognition.status is not RecognitionStatus.RECOGNIZED
            or recognition.recognition_date is None
        ):
            continue
        expenses.append(
            RecognizedInputExpense(
                invoice_id=invoice.id,
                recognition_date=recognition.recognition_date,
                amount=Decimal(str(invoice.total_amount)),
                is_tax_deductible=bool(invoice.is_tax_deductible),
                supplier_name=invoice.supplier_name,
                invoice_number=invoice.invoice_number,
                note=invoice.note,
                currency=invoice.currency or "BAM",
            )
        )
    return expenses
