from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
)


class ProfilePeriodIntegrityError(RuntimeError):
    """Profile history contains ambiguous effective-period coverage."""


def get_current_business_profile(
    db: Session,
    tenant_code: str,
) -> TenantBusinessProfileSettings | None:
    return db.execute(
        select(TenantBusinessProfileSettings).where(
            TenantBusinessProfileSettings.tenant_code == tenant_code,
            TenantBusinessProfileSettings.effective_to.is_(None),
        )
    ).scalar_one_or_none()


def get_current_tax_profile(
    db: Session,
    tenant_code: str,
) -> TenantTaxProfileSettings | None:
    return db.execute(
        select(TenantTaxProfileSettings).where(
            TenantTaxProfileSettings.tenant_code == tenant_code,
            TenantTaxProfileSettings.effective_to.is_(None),
        )
    ).scalar_one_or_none()


def _single_as_of_row(
    db: Session,
    *,
    model,
    tenant_code: str,
    as_of: date,
):
    # Legacy NULL/NULL profil namjerno NE dokazuje istorijski period.
    rows = db.execute(
        select(model)
        .where(
            model.tenant_code == tenant_code,
            model.effective_from.is_not(None),
            model.effective_from <= as_of,
            or_(
                model.effective_to.is_(None),
                model.effective_to >= as_of,
            ),
        )
        .order_by(
            model.effective_from.desc(),
            model.id.desc(),
        )
        .limit(2)
    ).scalars().all()

    if len(rows) > 1:
        raise ProfilePeriodIntegrityError(
            f"Overlapping effective profile periods for tenant={tenant_code}"
        )

    return rows[0] if rows else None


def get_business_profile_as_of(
    db: Session,
    tenant_code: str,
    as_of: date,
) -> TenantBusinessProfileSettings | None:
    return _single_as_of_row(
        db,
        model=TenantBusinessProfileSettings,
        tenant_code=tenant_code,
        as_of=as_of,
    )


def get_tax_profile_as_of(
    db: Session,
    tenant_code: str,
    as_of: date,
) -> TenantTaxProfileSettings | None:
    return _single_as_of_row(
        db,
        model=TenantTaxProfileSettings,
        tenant_code=tenant_code,
        as_of=as_of,
    )
