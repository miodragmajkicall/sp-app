from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


# ======================================================
#  GODIŠNJI SAŽECI
# ======================================================
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


# ======================================================
#  MJESEČNI SAŽECI
# ======================================================
class DashboardMonthlyCashSummary(BaseModel):
    """
    Mjesečni sažetak gotovinskog toka (cash_entries) za jednu godinu/mjesec.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina (YYYY).")
    month: int = Field(..., ge=1, le=12, description="Mjesec (1-12).")
    income_total: Decimal = Field(
        ...,
        description="Ukupan zbir prihoda (cash_entries.kind = 'income') za dati mjesec.",
    )
    expense_total: Decimal = Field(
        ...,
        description="Ukupan zbir rashoda (cash_entries.kind = 'expense') za dati mjesec.",
    )
    net_cashflow: Decimal = Field(
        ...,
        description="Neto cashflow = income_total - expense_total za dati mjesec.",
    )


class DashboardMonthlyInvoiceSummary(BaseModel):
    """
    Mjesečni sažetak izlaznih faktura za godinu/mjesec.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina (YYYY).")
    month: int = Field(..., ge=1, le=12, description="Mjesec (1-12).")
    invoices_count: int = Field(
        ...,
        description="Ukupan broj faktura u tom mjesecu.",
    )
    total_amount: Decimal = Field(
        ...,
        description="Ukupan iznos svih faktura (total_amount) u tom mjesecu.",
    )


class DashboardMonthlyTaxSummary(BaseModel):
    """
    Mjesečni sažetak poreznih rezultata (tax_monthly_results).

    Ključna polja su usklađena sa postojećim testovima:
    - has_result: da li postoji zapis za taj mjesec,
    - is_final: da li postoji bar jedan finalizovan zapis za taj mjesec.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina (YYYY).")
    month: int = Field(..., ge=1, le=12, description="Mjesec (1-12).")
    has_result: bool = Field(
        ...,
        description="Da li postoji barem jedan zapis u tax_monthly_results za ovaj period.",
    )
    is_final: bool = Field(
        ...,
        description="Da li postoji barem jedan zapis sa is_final = true za ovaj period.",
    )
    total_due: Decimal = Field(
        ...,
        description="Suma total_due iz svih zapisa u tax_monthly_results za ovaj period.",
    )


class DashboardMonthlySamSummary(BaseModel):
    """
    Mjesečni SAM sažetak – lightweight view na obaveze za jedan mjesec.

    Polja su usklađena sa testovima:
    - has_result: postoji li bilo kakav porezni rezultat,
    - is_final: da li je bar jedan rezultat finalizovan.
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina (YYYY).")
    month: int = Field(..., ge=1, le=12, description="Mjesec (1-12).")
    total_due: Decimal = Field(
        ...,
        description=(
            "Ukupna obaveza prema državi za ovaj mjesec. "
            "Trenutno direktno reflektuje DashboardMonthlyTaxSummary.total_due."
        ),
    )
    has_result: bool = Field(
        ...,
        description="Da li postoji bilo kakav porezni rezultat za ovaj mjesec.",
    )
    is_final: bool = Field(
        ...,
        description="Da li je bar jedan mjesečni rezultat finalizovan.",
    )


class DashboardMonthlySummary(BaseModel):
    """
    Kombinovani mjesečni dashboard za jednog tenanta:

    - cash summary za taj mjesec,
    - invoices summary za taj mjesec,
    - tax summary za taj mjesec,
    - sam summary za taj mjesec.
    """

    model_config = BaseConfig

    tenant_code: str = Field(..., description="Tenant kod.")
    year: int = Field(..., description="Godina (YYYY).")
    month: int = Field(..., ge=1, le=12, description="Mjesec (1-12).")

    cash: DashboardMonthlyCashSummary = Field(
        ..., description="Mjesečni sažetak gotovinskih tokova."
    )
    invoices: DashboardMonthlyInvoiceSummary = Field(
        ..., description="Mjesečni sažetak izlaznih faktura."
    )
    tax: DashboardMonthlyTaxSummary = Field(
        ..., description="Mjesečni sažetak poreznih rezultata."
    )
    sam: DashboardMonthlySamSummary = Field(
        ..., description="Mjesečni SAM sažetak.",
    )
