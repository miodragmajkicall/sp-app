from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CashEntry
from app.services.input_invoice_recognition import (
    RecognitionBasis,
    resolve_tenant_recognition_context,
)


class UnsupportedManualCashRecognitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecognizedManualCash:
    cash_entry_id: int
    recognition_date: date
    kind: Literal["income", "expense"]
    amount: Decimal
    tax_treatment: Literal["deductible", "nondeductible", "unresolved"] | None
    description: str | None


def list_recognized_manual_cash(
    db: Session,
    *,
    tenant_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    month: int | None = None,
) -> list[RecognizedManualCash]:
    """Return recognized manual business cash events for one tenant.

    Only unlinked CashEntry rows explicitly classified as business_activity
    participate in recognition. cash_only rows and linked invoice payments are
    excluded. Unsupported tenant recognition context fails closed whenever
    relevant business_activity rows exist in the requested period.
    """
    filters = [
        CashEntry.tenant_code == tenant_code,
        CashEntry.invoice_id.is_(None),
        CashEntry.input_invoice_id.is_(None),
        CashEntry.recognition_class == "business_activity",
    ]
    if date_from is not None:
        filters.append(CashEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(CashEntry.entry_date < date_to)
    if month is not None:
        filters.append(func.extract("month", CashEntry.entry_date) == month)

    stmt = (
        select(CashEntry)
        .where(*filters)
        .order_by(CashEntry.entry_date.asc(), CashEntry.id.asc())
    )

    rows = db.execute(stmt).scalars().all()
    if not rows:
        return []

    context = resolve_tenant_recognition_context(db, tenant_code)
    if context.basis is not RecognitionBasis.CASH:
        raise UnsupportedManualCashRecognitionError(
            "Manual cash recognition policy is not configured for this tenant"
        )

    return [
        RecognizedManualCash(
            cash_entry_id=row.id,
            recognition_date=row.entry_date,
            kind=row.kind,
            amount=Decimal(str(row.amount)),
            tax_treatment=row.tax_treatment,
            description=row.description,
        )
        for row in rows
    ]
