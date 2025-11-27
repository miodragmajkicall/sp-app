from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class DashboardCashSummary(BaseModel):
    """
    Sažetak gotovinskog toka (cash_entries) za jednu godinu.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina na koju se sažetak odnosi.")
    income_total: Decimal = Field(
        ...,
        description="Ukupan zbir prihoda (cash_entries.kind = 'income').",
    )
    expense_total: Decimal = Field(
        ...,
        description="Ukupan zbir rashoda (cash_entries.kind = 'expense').",
    )
    net_cashflow: Decimal = Field(
        ...,
        description="Neto cashflow = income_total - expense_total.",
    )


class DashboardInvoiceSummary(BaseModel):
    """
    Sažetak izlaznih faktura za jednu godinu.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina na koju se sažetak odnosi.")
    invoices_count: int = Field(
        ...,
        description="Ukupan broj faktura u toj godini.",
    )
    total_amount: Decimal = Field(
        ...,
        description="Ukupan iznos svih faktura (total_amount).",
    )


class DashboardTaxSummary(BaseModel):
    """
    Sažetak mjesečnih poreznih rezultata za jednu godinu.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina na koju se sažetak odnosi.")
    finalized_months: int = Field(
        ...,
        description=(
            "Broj mjeseci za koje postoji obračun u tax_monthly_results "
            "(trenutno ne razlikuje is_final vs. ne-finalizovano)."
        ),
    )
    total_due: Decimal = Field(
        ...,
        description="Ukupan zbir obaveza prema državi (suma total_due iz tax_monthly_results).",
    )


class DashboardSamSummary(BaseModel):
    """
    Sažetak SAM (obaveze prema državi) za jednu godinu.

    Ovo je lightweight bridge ka SAM modulu:
    - daje jednostavnu godišnju sumu za UI karticu,
    - i flag da li postoji bilo kakav obračun (da UI zna da li da pokaže 'prazno'
      ili 'aktivno' stanje).
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina na koju se SAM sažetak odnosi.")
    yearly_total_due: Decimal = Field(
        ...,
        description=(
            "Ukupna godišnja obaveza prema državi (suma total_due za sve mjesece). "
            "Trenutno direktno reflektuje DashboardTaxSummary.total_due."
        ),
    )
    has_any_finalized: bool = Field(
        ...,
        description=(
            "Da li postoji bar jedan zapis u tax_monthly_results za datu godinu "
            "(korisno za UI da zna da li je SAM modul 'prazan' ili ne)."
        ),
    )


class DashboardYearSummary(BaseModel):
    """
    Kombinovani yearly dashboard za jednog tenanta:

    - cash summary (income/expense/net),
    - invoices summary (broj + ukupno),
    - tax summary (broj obračunatih mjeseci + ukupna obaveza),
    - sam summary (godišnja obaveza + flag da li uopšte postoje obračuni).
    """

    model_config = BaseConfig

    tenant_code: str = Field(..., description="Tenant kod.")
    year: int = Field(..., description="Godina za koju je sažetak izračunat.")

    cash: DashboardCashSummary = Field(
        ..., description="Sažetak gotovinskih tokova."
    )
    invoices: DashboardInvoiceSummary = Field(
        ..., description="Sažetak izlaznih faktura."
    )
    tax: DashboardTaxSummary = Field(
        ..., description="Sažetak mjesečnih poreznih rezultata."
    )
    sam: DashboardSamSummary = Field(
        ...,
        description=(
            "Pojednostavljen SAM sažetak (godišnja obaveza + indikacija da li "
            "postoje obračuni)."
        ),
    )
