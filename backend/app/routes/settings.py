from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.tenant_security import require_tenant_code, ensure_tenant_exists
from app.models import (
    TenantProfileSettings,
    TenantTaxProfileSettings,
    TenantSubscriptionSettings,
)
from app.schemas.settings import (
    ProfileSettingsRead,
    ProfileSettingsUpsert,
    TaxProfileSettingsRead,
    TaxProfileSettingsUpsert,
    SubscriptionSettingsRead,
    SubscriptionSettingsUpsert,
)

router = APIRouter(prefix="/settings", tags=["settings"])


# ======================================================
#  PROFILE
# ======================================================
@router.get("/profile", response_model=ProfileSettingsRead)
def get_profile_settings(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantProfileSettings).where(
            TenantProfileSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        return ProfileSettingsRead(
            tenant_code=tenant,
            business_name=f"Tenant {tenant}",
        )

    return row


@router.put("/profile", response_model=ProfileSettingsRead)
def upsert_profile_settings(
    payload: ProfileSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantProfileSettings).where(
            TenantProfileSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        row = TenantProfileSettings(
            tenant_code=tenant,
            business_name=payload.business_name,
        )
        db.add(row)

    row.business_name = payload.business_name
    row.address = payload.address
    row.tax_id = payload.tax_id
    row.logo_attachment_id = payload.logo_attachment_id

    db.commit()
    db.refresh(row)
    return row


# ======================================================
#  TAX PROFILE
# ======================================================
@router.get("/tax", response_model=TaxProfileSettingsRead)
def get_tax_profile(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantTaxProfileSettings).where(
            TenantTaxProfileSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        return TaxProfileSettingsRead(
            tenant_code=tenant,
            entity="RS",
            regime="pausal",
            has_additional_activity=False,
        )

    return row


@router.put("/tax", response_model=TaxProfileSettingsRead)
def upsert_tax_profile(
    payload: TaxProfileSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantTaxProfileSettings).where(
            TenantTaxProfileSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        row = TenantTaxProfileSettings(
            tenant_code=tenant,
            entity=payload.entity,
            regime=payload.regime,
        )
        db.add(row)

    row.entity = payload.entity
    row.regime = payload.regime
    row.has_additional_activity = payload.has_additional_activity
    row.monthly_pension = payload.monthly_pension
    row.monthly_health = payload.monthly_health
    row.monthly_unemployment = payload.monthly_unemployment

    db.commit()
    db.refresh(row)
    return row


# ======================================================
#  SUBSCRIPTION
# ======================================================
@router.get("/subscription", response_model=SubscriptionSettingsRead)
def get_subscription(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantSubscriptionSettings).where(
            TenantSubscriptionSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        return SubscriptionSettingsRead(
            tenant_code=tenant,
            plan="Basic",
        )

    return row


@router.put("/subscription", response_model=SubscriptionSettingsRead)
def upsert_subscription(
    payload: SubscriptionSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantSubscriptionSettings).where(
            TenantSubscriptionSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        row = TenantSubscriptionSettings(
            tenant_code=tenant,
            plan=payload.plan,
        )
        db.add(row)

    row.plan = payload.plan

    db.commit()
    db.refresh(row)
    return row
