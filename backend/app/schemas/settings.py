# /home/miso/dev/sp-app/sp-app/backend/app/schemas/settings.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------- PROFILE ----------------
class ProfileSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str
    business_name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    swift_bic: Optional[str] = None

    # Back-compat:
    logo_attachment_id: Optional[int] = None

    # Novo:
    logo_asset_id: Optional[int] = None


class ProfileSettingsUpsert(BaseModel):
    business_name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=254)
    bank_name: Optional[str] = Field(default=None, max_length=128)
    bank_account: Optional[str] = Field(default=None, max_length=128)
    iban: Optional[str] = Field(default=None, max_length=64)
    swift_bic: Optional[str] = Field(default=None, max_length=32)

    # Back-compat:
    logo_attachment_id: Optional[int] = None

    # Novo (nećemo ga ručno unositi iz UI-ja, ali ga ostavljamo zbog API fleksibilnosti):
    logo_asset_id: Optional[int] = None

    @field_validator(
        "phone", "email", "bank_name", "bank_account", "iban", "swift_bic",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if any(character.isspace() for character in value) or value.count("@") != 1:
            raise ValueError("Invalid email address")
        local, domain = value.split("@")
        if (
            not local
            or not domain
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError("Invalid email address")
        return value


# ---------------- TAX PROFILE ----------------
class TaxProfileSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str
    entity: str
    regime: str

    # Novo: primarni izbor scenarija
    scenario_key: Optional[str] = None

    has_additional_activity: bool
    monthly_pension: Optional[float] = None
    monthly_health: Optional[float] = None
    monthly_unemployment: Optional[float] = None


class TaxProfileSettingsUpsert(BaseModel):
    entity: str = Field(..., examples=["RS", "FBiH", "Brcko"])
    regime: str = Field(..., examples=["pausal", "two_percent"])

    # Novo: opcioni upsert scenario_key (back-compat: može biti None)
    scenario_key: Optional[str] = Field(
        default=None,
        examples=["rs_primary", "rs_supplementary", "fbih_obrt", "fbih_slobodna", "bd_samostalna"],
    )

    has_additional_activity: bool = False
    monthly_pension: Optional[float] = None
    monthly_health: Optional[float] = None
    monthly_unemployment: Optional[float] = None


class TaxScenarioOption(BaseModel):
    key: str
    label: str
    hint: Optional[str] = None
    entity: str = Field(..., examples=["RS", "FBiH", "Brcko"])


# ---------------- SUBSCRIPTION ----------------
class SubscriptionSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str
    plan: str


class SubscriptionSettingsUpsert(BaseModel):
    plan: str = Field(..., examples=["Basic", "Standard", "Premium"])
