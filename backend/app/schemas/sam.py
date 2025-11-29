from __future__ import annotations

from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


# Osnovna Pydantic konfiguracija, ista filozofija kao kod ostalih šema
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class SamMonthlyItem(BaseModel):
    """
    Jedan mjesecni blok za SAM overview.

    Ovo je osnovni building-block za UI grafove i tabele:
    - mjesec (1-12)
    - labela za prikaz (npr. "01.2025")
    - agregirani iznosi i flag da li je mjesec zaključen.
    """

    model_config = BaseConfig

    month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Redni broj mjeseca (1-12).",
    )
    month_label: str = Field(
        ...,
        description="Prikaz mjeseca za UI (npr. '01.2025' ili 'JAN 2025').",
    )

    income_total: Decimal = Field(
        ...,
        description="Ukupan prihod za dati mjesec.",
    )
    expense_total: Decimal = Field(
        ...,
        description="Ukupan rashod za dati mjesec.",
    )
    tax_base: Decimal = Field(
        ...,
        description="Oporeziva osnovica za mjesec.",
    )
    tax_due: Decimal = Field(
        ...,
        description="Porez za mjesec.",
    )
    contributions_due: Decimal = Field(
        ...,
        description="Doprinosi za mjesec.",
    )
    total_due: Decimal = Field(
        ...,
        description="Ukupno za uplatu (porez + doprinosi) za taj mjesec.",
    )

    is_finalized: bool = Field(
        ...,
        description="Da li je porezni obračun za ovaj mjesec finaliziran.",
    )


class SamYearlySummary(BaseModel):
    """
    Godišnji sažetak za SAM overview.

    Na nivou godine agregira:
    - sve prihode/rashode,
    - sve poreze i doprinose,
    - broj zaključenih i otvorenih mjeseci.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina na koju se odnosi pregled.")

    income_total: Decimal = Field(
        ...,
        description="Ukupan godišnji prihod.",
    )
    expense_total: Decimal = Field(
        ...,
        description="Ukupan godišnji rashod.",
    )
    tax_base_total: Decimal = Field(
        ...,
        description="Ukupna godišnja oporeziva osnovica.",
    )
    tax_due_total: Decimal = Field(
        ...,
        description="Ukupan godišnji porez.",
    )
    contributions_due_total: Decimal = Field(
        ...,
        description="Ukupni godišnji doprinosi.",
    )
    total_due: Decimal = Field(
        ...,
        description="Ukupno za uplatu državi za cijelu godinu.",
    )

    finalized_months: int = Field(
        ...,
        ge=0,
        le=12,
        description="Broj mjeseci za koje je obračun finaliziran.",
    )
    open_months: int = Field(
        ...,
        ge=0,
        le=12,
        description="Broj mjeseci koji su još otvoreni (nisu finalizirani).",
    )


class SamOverviewRead(BaseModel):
    """
    Kombinovani SAM overview odgovor za jedan tenant i jednu godinu.

    Ovo je direktni shape za dashboard:
    - tenant_code,
    - godina,
    - lista 12 mjeseci,
    - godišnji sažetak.
    """

    model_config = BaseConfig

    tenant_code: str = Field(
        ...,
        description="Tenant (SP) za kojeg se prikazuje SAM pregled.",
    )
    year: int = Field(
        ...,
        description="Godina SAM pregleda.",
    )

    months: List[SamMonthlyItem] = Field(
        ...,
        description="Lista 12 mjeseci sa agregatima (uvijek 12 elemenata).",
    )
    yearly_summary: SamYearlySummary = Field(
        ...,
        description="Godišnji sažetak obaveza prema državi.",
    )
