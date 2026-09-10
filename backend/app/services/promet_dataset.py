from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import CashEntry, Invoice
from app.services.promet_eligibility import PrometMode


class UnsupportedPrometDatasetModeError(RuntimeError):
    pass


class PrometSourceType(str, Enum):
    OUTGOING_INVOICE_PAYMENT = "outgoing_invoice_payment"
    MANUAL_BUSINESS_INCOME = "manual_business_income"


@dataclass(frozen=True)
class CanonicalPrometEvent:
    mode: PrometMode
    event_date: date
    source_type: PrometSourceType
    source_id: int
    source_document_id: int | None
    document_number: str | None
    counterparty_name: str | None
    counterparty_type: str | None
    counterparty_tax_id: str | None
    payment_channel: Literal["cash", "bank"]
    amount: Decimal
    description: str | None


def _build_rs_canonical_source_stmt(
    *,
    tenant_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
):
    filters = [
        CashEntry.tenant_code == tenant_code,
        CashEntry.kind == "income",
        or_(
            CashEntry.invoice_id.is_not(None),
            and_(
                CashEntry.invoice_id.is_(None),
                CashEntry.input_invoice_id.is_(None),
                CashEntry.recognition_class == "business_activity",
            ),
        ),
    ]

    if date_from is not None:
        filters.append(CashEntry.entry_date >= date_from)

    if date_to is not None:
        filters.append(CashEntry.entry_date <= date_to)

    return (
        select(CashEntry, Invoice)
        .outerjoin(
            Invoice,
            and_(
                Invoice.id == CashEntry.invoice_id,
                Invoice.tenant_code == CashEntry.tenant_code,
            ),
        )
        .where(*filters)
    )


def list_canonical_promet_events(
    db: Session,
    *,
    tenant_code: str,
    mode: PrometMode,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CanonicalPrometEvent]:
    """
    Return canonical source events for one Promet mode.

    This is a source-event layer, not yet a statutory-form projection.

    Currently implemented:
    - RS_SMALL_ENTREPRENEUR

    Fail closed for modes whose statutory dataset cannot yet be built
    from the facts stored by EVIDENT.
    """
    if mode is not PrometMode.RS_SMALL_ENTREPRENEUR:
        raise UnsupportedPrometDatasetModeError(
            f"Promet dataset mode is not implemented: {mode.value}"
        )

    stmt = _build_rs_canonical_source_stmt(
        tenant_code=tenant_code,
        date_from=date_from,
        date_to=date_to,
    ).order_by(
        CashEntry.entry_date.asc(),
        CashEntry.id.asc(),
    )

    rows = db.execute(stmt).all()
    events: list[CanonicalPrometEvent] = []

    for cash_entry, invoice in rows:
        amount = Decimal(str(cash_entry.amount))

        if amount <= 0:
            raise RuntimeError(
                "Promet income source must have a positive amount"
            )

        if cash_entry.invoice_id is not None:
            if invoice is None:
                raise RuntimeError(
                    "Outgoing invoice payment points to an unavailable "
                    "invoice for this tenant"
                )

            events.append(
                CanonicalPrometEvent(
                    mode=mode,
                    event_date=cash_entry.entry_date,
                    source_type=(
                        PrometSourceType.OUTGOING_INVOICE_PAYMENT
                    ),
                    source_id=cash_entry.id,
                    source_document_id=invoice.id,
                    document_number=invoice.invoice_number,
                    counterparty_name=invoice.buyer_name,
                    counterparty_type=invoice.buyer_type,
                    counterparty_tax_id=invoice.buyer_tax_id,
                    payment_channel=cash_entry.account,
                    amount=amount,
                    description=cash_entry.description,
                )
            )
            continue

        events.append(
            CanonicalPrometEvent(
                mode=mode,
                event_date=cash_entry.entry_date,
                source_type=PrometSourceType.MANUAL_BUSINESS_INCOME,
                source_id=cash_entry.id,
                source_document_id=None,
                # Ne izmišljamo CE-<id> kao broj pravnog dokumenta.
                document_number=None,
                counterparty_name=None,
                counterparty_type=None,
                counterparty_tax_id=None,
                payment_channel=cash_entry.account,
                amount=amount,
                description=cash_entry.description,
            )
        )

    return events
