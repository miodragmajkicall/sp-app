# /home/miso/dev/sp-app/sp-app/backend/app/schemas/settings.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------- PROFILE ----------------
class ProfileSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str
    business_name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None

    # Back-compat:
    logo_attachment_id: Optional[int] = None

    # Novo:
    logo_asset_id: Optional[int] = None


class ProfileSettingsUpsert(BaseModel):
    business_name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None

    # Back-compat:
    logo_attachment_id: Optional[int] = None

    # Novo (nećemo ga ručno unositi iz UI-ja, ali ga ostavljamo zbog API fleksibilnosti):
    logo_asset_id: Optional[int] = None


# ---------------- TAX PROFILE ----------------
class TaxProfileSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str
    entity: str
    regime: str
    has_additional_activity: bool
    monthly_pension: Optional[float] = None
    monthly_health: Optional[float] = None
    monthly_unemployment: Optional[float] = None


class TaxProfileSettingsUpsert(BaseModel):
    entity: str = Field(..., examples=["RS", "FBiH", "Brcko"])
    regime: str = Field(..., examples=["pausal", "two_percent"])
    has_additional_activity: bool = False
    monthly_pension: Optional[float] = None
    monthly_health: Optional[float] = None
    monthly_unemployment: Optional[float] = None


# ---------------- SUBSCRIPTION ----------------
class SubscriptionSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str
    plan: str


class SubscriptionSettingsUpsert(BaseModel):
    plan: str = Field(..., examples=["Basic", "Standard", "Premium"])
