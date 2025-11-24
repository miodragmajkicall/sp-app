from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


# Osnovna Pydantic konfiguracija (isti pattern kao kod cash/invoices):
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class TaxDummyConfig(BaseModel):
    """
    DUMMY konfiguracija poreza i doprinosa.

    Ovo NIJE pravni savjet niti tačan model poreskog sistema.
    Služi isključivo za razvoj i testiranje obračuna u aplikaciji.
    """

    model_config = BaseConfig

    income_tax_rate: Decimal = Field(
        ...,
        description=(
            "Stopa poreza na dohodak. "
            "Primjer: 0.10 znači 10% poreza na oporezivu osnovicu."
        ),
        examples=[Decimal("0.10")],
    )
    pension_contribution_rate: Decimal = Field(
        ...,
        description=(
            "Stopa doprinosa za PIO (penziono). "
            "Primjer: 0.18 znači 18% na odgovarajuću osnovicu."
        ),
        examples=[Decimal("0.18")],
    )
    health_contribution_rate: Decimal = Field(
        ...,
        description=(
            "Stopa doprinosa za zdravstveno osiguranje. "
            "Primjer: 0.12 znači 12%."
        ),
        examples=[Decimal("0.12")],
    )
    unemployment_contribution_rate: Decimal = Field(
        ...,
        description=(
            "Stopa doprinosa za osiguranje od nezaposlenosti. "
            "Primjer: 0.015 znači 1.5%."
        ),
        examples=[Decimal("0.015")],
    )
    flat_costs_rate: Decimal = Field(
        ...,
        description=(
            "Procenat priznatih paušalnih troškova. "
            "Primjer: 0.30 znači da se 30% prihoda tretira kao trošak. "
            "Ovo je DUMMY vrijednost isključivo za simulaciju u aplikaciji."
        ),
        examples=[Decimal("0.30")],
    )
    currency: str = Field(
        "BAM",
        description="Valuta u kojoj se vrši obračun (podrazumijevano 'BAM').",
        examples=["BAM"],
    )


class MonthlyTaxSummaryRead(BaseModel):
    """
    Reprezentacija MJESEČNOG poreznog obračuna za jednog tenanta.

    Ovaj model se koristi za READ/preview scenarije:
    - sumarizacija prihoda/rashoda iz postojeće evidencije (cash + invoices),
    - izračun osnovice,
    - izračun poreza i doprinosa,
    - prikaz ukupne obaveze za uplatu.
    """

    model_config = BaseConfig

    year: int = Field(
        ...,
        ge=2000,
        le=2100,
        description="Godina obračuna (YYYY).",
        examples=[2025],
    )
    month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Mjesec obračuna (1-12).",
        examples=[1],
    )

    tenant_code: Optional[str] = Field(
        None,
        description=(
            "Kod tenanta na kog se odnosi obračun. "
            "Ovo je opcioni prikazni podatak – u većini slučajeva "
            "tenant se određuje preko X-Tenant-Code headera."
        ),
        examples=["t-demo"],
    )

    total_income: Decimal = Field(
        ...,
        ge=0,
        description="Ukupan iznos prihoda za dati period (suma svih relevantnih ulaza).",
        examples=[Decimal("5000.00")],
    )
    total_expense: Decimal = Field(
        ...,
        ge=0,
        description="Ukupan iznos rashoda za dati period.",
        examples=[Decimal("1500.00")],
    )

    taxable_base: Decimal = Field(
        ...,
        description=(
            "Osnovica za oporezivanje nakon primjene paušalnih troškova "
            "i ostalih umanjenja. Tipično: (total_income - priznati_troškovi)."
        ),
        examples=[Decimal("3500.00")],
    )

    income_tax: Decimal = Field(
        ...,
        description="Iznos poreza na dohodak za dati period.",
        examples=[Decimal("350.00")],
    )
    contributions_total: Decimal = Field(
        ...,
        description=(
            "Zbir svih doprinosa (PIO, zdravstveno, nezaposlenost, itd.) "
            "za dati period."
        ),
        examples=[Decimal("900.00")],
    )

    total_due: Decimal = Field(
        ...,
        description=(
            "Ukupna obaveza za uplatu (porez + doprinosi) za dati period. "
            "Ovo je glavni broj koji SP korisnika zanima."
        ),
        examples=[Decimal("1250.00")],
    )

    is_final: bool = Field(
        False,
        description=(
            "Da li je ovaj mjesečni obračun označen kao finaliziran (zaključan) "
            "u sistemu. Za početak će se koristiti samo za prikaz (preview), "
            "kasnije možemo dodati mehanizam 'zaključavanja' obračuna."
        ),
        examples=[False],
    )

    currency: str = Field(
        "BAM",
        description="Valuta u kojoj su izraženi svi iznosi.",
        examples=["BAM"],
    )
