# /home/miso/dev/sp-app/sp-app/backend/app/schemas/tax.py
from __future__ import annotations

from datetime import date
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
            "Stopa poreza na dohodak.\n\n"
            "Primjer: 0.10 znači 10% poreza na oporezivu osnovicu."
        ),
        examples=[Decimal("0.10")],
    )
    pension_contribution_rate: Decimal = Field(
        ...,
        description=(
            "Stopa doprinosa za PIO (penziono).\n\n"
            "Primjer: 0.18 znači 18% na odgovarajuću osnovicu."
        ),
        examples=[Decimal("0.18")],
    )
    health_contribution_rate: Decimal = Field(
        ...,
        description=(
            "Stopa doprinosa za zdravstveno osiguranje.\n\n"
            "Primjer: 0.12 znači 12%."
        ),
        examples=[Decimal("0.12")],
    )
    unemployment_contribution_rate: Decimal = Field(
        ...,
        description=(
            "Stopa doprinosa za osiguranje od nezaposlenosti.\n\n"
            "Primjer: 0.015 znači 1.5%."
        ),
        examples=[Decimal("0.015")],
    )
    flat_costs_rate: Decimal = Field(
        ...,
        description=(
            "Procenat priznatih paušalnih troškova.\n\n"
            "Primjer: 0.30 znači da se 30% prihoda tretira kao trošak.\n"
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
            "Kod tenanta na kog se odnosi obračun.\n"
            "Ovo je opcioni prikazni podatak – u većini slučajeva "
            "tenant se određuje preko `X-Tenant-Code` headera."
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
            "i ostalih umanjenja.\n"
            "Tipično: `total_income - priznati_troškovi - total_expense`."
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
            "Ukupna obaveza za uplatu (porez + doprinosi) za dati period.\n"
            "Ovo je glavni broj koji SP korisnika zanima."
        ),
        examples=[Decimal("1250.00")],
    )

    is_final: bool = Field(
        False,
        description=(
            "Da li je ovaj mjesečni obračun označen kao finaliziran (zaključan) "
            "u sistemu.\n"
            "Kod preview/auto obračuna je obično `false`, a kod finalizovanih "
            "rezultata `true`."
        ),
        examples=[False],
    )

    currency: str = Field(
        "BAM",
        description="Valuta u kojoj su izraženi svi iznosi.",
        examples=["BAM"],
    )


class ErrorResponse(BaseModel):
    """
    Standardizovani model za opis grešaka na TAX endpointima.
    """

    model_config = BaseConfig

    detail: str = Field(
        ...,
        description="Ljudski čitljiv opis greške.",
        examples=[
            "Missing X-Tenant-Code header",
            "Monthly tax result for this period is already finalized",
        ],
    )


class MonthlyTaxStatusItem(BaseModel):
    model_config = BaseConfig

    month: int = Field(..., ge=1, le=12, description="Mjesec u godini (1-12).", examples=[1])
    is_final: bool = Field(..., description="Da li postoji finalizovan obračun.", examples=[True])
    has_data: bool = Field(..., description="Da li postoji bilo kakav obračun.", examples=[True])


class MonthlyTaxStatusResponse(BaseModel):
    model_config = BaseConfig

    year: int = Field(..., ge=2000, le=2100, description="Godina.", examples=[2025])
    tenant_code: str = Field(..., description="Šifra tenanta.", examples=["t-demo"])
    items: list[MonthlyTaxStatusItem] = Field(..., description="Lista statusa po mjesecima (1-12).")


class YearlyTaxSummaryRead(BaseModel):
    model_config = BaseConfig

    year: int = Field(..., ge=2000, le=2100, description="Godina.", examples=[2025])
    tenant_code: str = Field(..., description="Šifra tenanta.", examples=["t-demo"])

    months_included: int = Field(..., ge=0, le=12, description="Broj uključenih mjeseci.", examples=[12])

    total_income: Decimal = Field(..., ge=0, description="Zbir prihoda.", examples=[Decimal("60000.00")])
    total_expense: Decimal = Field(..., ge=0, description="Zbir rashoda.", examples=[Decimal("18000.00")])
    taxable_base: Decimal = Field(..., description="Zbir osnovice.", examples=[Decimal("42000.00")])
    income_tax: Decimal = Field(..., description="Zbir poreza.", examples=[Decimal("4200.00")])
    contributions_total: Decimal = Field(..., description="Zbir doprinosa.", examples=[Decimal("10800.00")])
    total_due: Decimal = Field(..., description="Ukupno za uplatu.", examples=[Decimal("15000.00")])
    currency: str = Field("BAM", description="Valuta.", examples=["BAM"])


# ======================================================
#  10.1 /tax/monthly – mjesečni pregled (12 mjeseci + status uplate)
# ======================================================
class TaxMonthlyOverviewItem(BaseModel):
    """
    Jedan mjesec u godišnjem pregledu poreskih obaveza (10.1).

    Svi iznosi su u valuti (default BAM).
    """

    model_config = BaseConfig

    year: int = Field(..., ge=2000, le=2100, examples=[2025])
    month: int = Field(..., ge=1, le=12, examples=[1])

    # iznosi po zahtjevu:
    income_tax: Decimal = Field(..., ge=0, description="Paušalni porez (KM).", examples=[Decimal("350.00")])
    pension: Decimal = Field(..., ge=0, description="PIO (KM).", examples=[Decimal("630.00")])
    health: Decimal = Field(..., ge=0, description="Zdravstveno (KM).", examples=[Decimal("420.00")])
    unemployment: Decimal = Field(..., ge=0, description="Nezaposlenost (KM).", examples=[Decimal("52.50")])
    total_due: Decimal = Field(..., ge=0, description="Total (KM).", examples=[Decimal("1452.50")])

    # status uplate:
    is_paid: bool = Field(False, description="Status uplate (DA/NE).", examples=[False])
    paid_at: Optional[date] = Field(None, description="Datum uplate.", examples=["2025-01-15"])

    currency: str = Field("BAM", description="Valuta.", examples=["BAM"])


class TaxMonthlyOverviewResponse(BaseModel):
    model_config = BaseConfig

    year: int = Field(..., ge=2000, le=2100, examples=[2025])
    tenant_code: str = Field(..., examples=["t-demo"])
    items: list[TaxMonthlyOverviewItem] = Field(..., description="Lista 12 mjeseci (1-12).")


class TaxMonthlyPaymentUpsert(BaseModel):
    """
    Payload za označavanje uplate.

    Pravila:
    - ako is_paid=true i paid_at nije poslan → backend upisuje današnji datum
    - ako is_paid=false → paid_at se briše (postaje null)
    """

    model_config = BaseConfig

    is_paid: bool = Field(..., description="Da li je uplata izvršena.", examples=[True])
    paid_at: Optional[date] = Field(None, description="Datum uplate (opciono).", examples=["2025-01-15"])
