from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FinalizedPeriodModificationError, TaxMonthlyResult


def ensure_period_open(
    db: Session,
    *,
    tenant_code: str,
    period_date: date | None,
) -> None:
    if period_date is None:
        return

    finalized_id = db.execute(
        select(TaxMonthlyResult.id).where(
            TaxMonthlyResult.tenant_code == tenant_code,
            TaxMonthlyResult.year == period_date.year,
            TaxMonthlyResult.month == period_date.month,
            TaxMonthlyResult.is_final.is_(True),
        )
    ).scalar_one_or_none()
    if finalized_id is not None:
        raise FinalizedPeriodModificationError(
            tenant_code=tenant_code,
            year=period_date.year,
            month=period_date.month,
        )
