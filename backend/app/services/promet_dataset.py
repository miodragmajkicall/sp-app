from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal

from sqlalchemy import and_, case, func, or_, select, true
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


@dataclass(frozen=True)
class CanonicalPrometPage:
    total: int
    total_amount: Decimal
    cash_amount: Decimal
    bank_amount: Decimal
    items: tuple[CanonicalPrometEvent, ...]


def _require_rs_promet_mode(mode: PrometMode) -> None:
    if mode is not PrometMode.RS_SMALL_ENTREPRENEUR:
        raise UnsupportedPrometDatasetModeError(
            f"Promet dataset mode is not implemented: {mode.value}"
        )


def _build_rs_canonical_source_stmt(
    *,
    tenant_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    columns=None,
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

    selected_columns = (
        columns
        if columns is not None
        else (CashEntry, Invoice)
    )

    return (
        select(*selected_columns)
        .outerjoin(
            Invoice,
            and_(
                Invoice.id == CashEntry.invoice_id,
                Invoice.tenant_code == CashEntry.tenant_code,
            ),
        )
        .where(*filters)
    )


def _canonical_promet_event_from_row(
    *,
    cash_entry: CashEntry,
    invoice: Invoice | None,
    mode: PrometMode,
) -> CanonicalPrometEvent:
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

        return CanonicalPrometEvent(
            mode=mode,
            event_date=cash_entry.entry_date,
            source_type=PrometSourceType.OUTGOING_INVOICE_PAYMENT,
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

    return CanonicalPrometEvent(
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


def query_canonical_promet_page(
    db: Session,
    *,
    tenant_code: str,
    mode: PrometMode,
    year: int | None = None,
    month: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> CanonicalPrometPage:
    """
    Return one optimized canonical Promet page.

    The canonical source and source validation are scoped by
    date_from/date_to. Year/month narrow only the list/summary dataset,
    matching the existing /promet contract.

    Partner search intentionally remains outside this optimized path.
    """
    _require_rs_promet_mode(mode)

    if limit < 1:
        raise ValueError("Promet page limit must be positive")

    if offset < 0:
        raise ValueError("Promet page offset cannot be negative")

    source = _build_rs_canonical_source_stmt(
        tenant_code=tenant_code,
        date_from=date_from,
        date_to=date_to,
        columns=(
            CashEntry.id.label("source_id"),
            CashEntry.entry_date.label("event_date"),
            CashEntry.amount.label("amount"),
            CashEntry.account.label("payment_channel"),
            CashEntry.invoice_id.label("invoice_id"),
            Invoice.id.label("joined_invoice_id"),
        ),
    ).cte("promet_source")

    missing_invoice = and_(
        source.c.invoice_id.is_not(None),
        source.c.joined_invoice_id.is_(None),
    )

    invalid_code = case(
        (source.c.amount <= 0, "nonpositive_amount"),
        (missing_invoice, "missing_invoice"),
        else_=None,
    )

    first_invalid_code = (
        select(invalid_code)
        .where(
            or_(
                source.c.amount <= 0,
                missing_invoice,
            )
        )
        .order_by(
            source.c.event_date.asc(),
            source.c.source_id.asc(),
        )
        .limit(1)
        .scalar_subquery()
    )

    filtered_conditions = []

    if year is not None:
        if month is not None:
            period_start = date(year, month, 1)
            period_end = (
                date(year + 1, 1, 1)
                if month == 12
                else date(year, month + 1, 1)
            )
        else:
            period_start = date(year, 1, 1)
            period_end = date(year + 1, 1, 1)

        filtered_conditions.extend(
            [
                source.c.event_date >= period_start,
                source.c.event_date < period_end,
            ]
        )
    elif month is not None:
        filtered_conditions.append(
            func.extract("month", source.c.event_date) == month
        )

    filtered_stmt = select(source)

    if filtered_conditions:
        filtered_stmt = filtered_stmt.where(*filtered_conditions)

    filtered = filtered_stmt.cte("promet_filtered")

    stats = (
        select(
            func.count().label("total"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            filtered.c.payment_channel == "cash",
                            filtered.c.amount,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("cash_amount"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            filtered.c.payment_channel == "bank",
                            filtered.c.amount,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("bank_amount"),
        )
        .select_from(filtered)
        .cte("promet_stats")
    )

    page_rows = (
        select(
            filtered.c.source_id,
            filtered.c.event_date,
            filtered.c.joined_invoice_id,
        )
        .order_by(
            filtered.c.event_date.desc(),
            filtered.c.source_id.desc(),
        )
        .limit(limit)
        .offset(offset)
        .cte("promet_page_rows")
    )

    stmt = (
        select(
            CashEntry,
            Invoice,
            stats.c.total,
            stats.c.cash_amount,
            stats.c.bank_amount,
            first_invalid_code.label("invalid_code"),
        )
        .select_from(stats)
        .outerjoin(page_rows, true())
        .outerjoin(
            CashEntry,
            CashEntry.id == page_rows.c.source_id,
        )
        .outerjoin(
            Invoice,
            Invoice.id == page_rows.c.joined_invoice_id,
        )
        .order_by(
            page_rows.c.event_date.desc().nulls_last(),
            page_rows.c.source_id.desc().nulls_last(),
        )
    )

    rows = db.execute(stmt).all()

    if not rows:
        raise RuntimeError("Promet optimized query returned no stats row")

    invalid = rows[0].invalid_code

    if invalid == "nonpositive_amount":
        raise RuntimeError(
            "Promet income source must have a positive amount"
        )

    if invalid == "missing_invoice":
        raise RuntimeError(
            "Outgoing invoice payment points to an unavailable "
            "invoice for this tenant"
        )

    total = int(rows[0].total or 0)
    cash_amount = Decimal(str(rows[0].cash_amount or Decimal("0.00")))
    bank_amount = Decimal(str(rows[0].bank_amount or Decimal("0.00")))

    items = tuple(
        _canonical_promet_event_from_row(
            cash_entry=row.CashEntry,
            invoice=row.Invoice,
            mode=mode,
        )
        for row in rows
        if row.CashEntry is not None
    )

    return CanonicalPrometPage(
        total=total,
        total_amount=cash_amount + bank_amount,
        cash_amount=cash_amount,
        bank_amount=bank_amount,
        items=items,
    )


def get_canonical_promet_date_bounds(
    db: Session,
    *,
    tenant_code: str,
    mode: PrometMode,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[date | None, date | None]:
    """
    Return min/max event_date from the canonical Promet source scope.

    This helper discovers the real data span only. Canonical source integrity
    validation remains the responsibility of the existing dataset readers.
    """
    _require_rs_promet_mode(mode)

    source = _build_rs_canonical_source_stmt(
        tenant_code=tenant_code,
        date_from=date_from,
        date_to=date_to,
        columns=(
            CashEntry.entry_date.label("event_date"),
        ),
    ).subquery("promet_date_source")

    minimum_date, maximum_date = db.execute(
        select(
            func.min(source.c.event_date),
            func.max(source.c.event_date),
        )
    ).one()

    return minimum_date, maximum_date


def list_canonical_promet_years_for_month(
    db: Session,
    *,
    tenant_code: str,
    mode: PrometMode,
    month: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[int, ...]:
    """
    Return sorted years that contain canonical Promet source events
    in the requested calendar month.

    month-only Promet filtering means that month across all years, so gaps
    between those calendar months must not be treated as requested coverage.
    """
    _require_rs_promet_mode(mode)

    if month < 1 or month > 12:
        raise ValueError("Promet month must be between 1 and 12")

    source = _build_rs_canonical_source_stmt(
        tenant_code=tenant_code,
        date_from=date_from,
        date_to=date_to,
        columns=(
            CashEntry.entry_date.label("event_date"),
        ),
    ).subquery("promet_month_source")

    year_expr = func.extract("year", source.c.event_date)

    years = db.execute(
        select(year_expr)
        .where(
            func.extract("month", source.c.event_date) == month
        )
        .distinct()
        .order_by(year_expr.asc())
    ).scalars().all()

    return tuple(int(year) for year in years)


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
    _require_rs_promet_mode(mode)

    stmt = _build_rs_canonical_source_stmt(
        tenant_code=tenant_code,
        date_from=date_from,
        date_to=date_to,
    ).order_by(
        CashEntry.entry_date.asc(),
        CashEntry.id.asc(),
    )

    rows = db.execute(stmt).all()
    events = [
        _canonical_promet_event_from_row(
            cash_entry=cash_entry,
            invoice=invoice,
            mode=mode,
        )
        for cash_entry, invoice in rows
    ]

    return events
