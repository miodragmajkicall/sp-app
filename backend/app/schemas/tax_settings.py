# /home/miso/dev/sp-app/sp-app/backend/app/schemas/tax_settings.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TaxSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_code: str

    income_tax_rate: Decimal
    pension_contribution_rate: Decimal
    health_contribution_rate: Decimal
    unemployment_contribution_rate: Decimal
    flat_costs_rate: Decimal

    currency: str


class TaxSettingsUpsert(BaseModel):
    """
    Upsert payload: sva polja su opciona da UI može mijenjati postepeno.
    Backend će za missing polja zadržati postojeće vrijednosti ili default.
    """

    income_tax_rate: Optional[Decimal] = Field(None, ge=0)
    pension_contribution_rate: Optional[Decimal] = Field(None, ge=0)
    health_contribution_rate: Optional[Decimal] = Field(None, ge=0)
    unemployment_contribution_rate: Optional[Decimal] = Field(None, ge=0)
    flat_costs_rate: Optional[Decimal] = Field(None, ge=0)

    currency: Optional[str] = Field(None, min_length=1, max_length=8)
