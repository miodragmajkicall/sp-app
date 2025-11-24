from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Invoice
from app.schemas.tax import TaxDummyConfig, MonthlyTaxSummaryRead

router = APIRouter(
    tags=["tax"],
)


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Osigurava da je X-Tenant-Code header postavljen.
    Ako nedostaje, vraća HTTP 400.

    Ovaj helper je identičan konceptu iz invoices/cash modula – radi konzistentnosti.
    """
    if not x_tenant_code:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Code header")
    return x_tenant_code


# DUMMY konfiguracija – koristi se isključivo za razvoj i testiranje.
# Kasnije se može zamijeniti dinamičkom konfiguracijom po tenantu ili iz baze.
TAX_DUMMY_CONFIG = TaxDummyConfig(
    income_tax_rate=Decimal("0.10"),  # 10% poreza na dohodak
    pension_contribution_rate=Decimal("0.18"),  # 18% PIO
    health_contribution_rate=Decimal("0.12"),  # 12% zdravstveno
    unemployment_contribution_rate=Decimal("0.015"),  # 1.5% nezaposlenost
    flat_costs_rate=Decimal("0.30"),  # 30% priznati paušalni troškovi
)


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """
    Vraća (start, end) granice mjeseca:
    - start = prvi dan mjeseca (uključivo)
    - end   = prvi dan sljedećeg mjeseca (isključivo)
    """
    if month == 12:
        start = date(year, 12, 1)
        end = date(year + 1, 1, 1)
    else:
        start = date(year, month, 1)
        end = date(year, month + 1, 1)
    return start, end


def _compute_monthly_summary(
    *,
    year: int,
    month: int,
    tenant_code: str,
    total_income: Decimal,
    total_expense: Decimal,
    cfg: TaxDummyConfig,
) -> MonthlyTaxSummaryRead:
    """
    Zajednička logika obračuna mjesečnog poreza/doprinosa.

    Koriste je i /tax/monthly/preview (ručni input) i /tax/monthly/auto (iz baze).
    """

    # 1) Paušalni troškovi
    flat_costs = total_income * cfg.flat_costs_rate

    # 2) Osnovica za oporezivanje
    taxable_base = total_income - flat_costs - total_expense
    if taxable_base < Decimal("0"):
        taxable_base = Decimal("0.00")

    # 3) Porez na dohodak
    income_tax = taxable_base * cfg.income_tax_rate

    # 4) Doprinosi (zbirno)
    contributions_rate_sum = (
        cfg.pension_contribution_rate
        + cfg.health_contribution_rate
        + cfg.unemployment_contribution_rate
    )
    contributions_total = taxable_base * contributions_rate_sum

    # 5) Ukupna obaveza
    total_due = income_tax + contributions_total

    return MonthlyTaxSummaryRead(
        year=year,
        month=month,
        tenant_code=tenant_code,
        total_income=total_income,
        total_expense=total_expense,
        taxable_base=taxable_base,
        income_tax=income_tax,
        contributions_total=contributions_total,
        total_due=total_due,
        is_final=False,
        currency=cfg.currency,
    )


@router.get(
    "/tax/monthly/preview",
    response_model=MonthlyTaxSummaryRead,
    summary="Preview mjesečnog poreznog obračuna (DUMMY)",
)
def preview_monthly_tax(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
        description="Godina obračuna (YYYY).",
        examples=[2025],
    ),
    month: int = Query(
        ...,
        ge=1,
        le=12,
        description="Mjesec obračuna (1-12).",
        examples=[1],
    ),
    total_income: Decimal = Query(
        ...,
        ge=0,
        description=(
            "Ukupan iznos prihoda za dati period koji ulazi u simulaciju obračuna.\n\n"
            "U prvoj fazi se ovdje ručno prosleđuje suma prihoda (npr. iz invoices/cash), "
            "a kasnije će backend sam povlačiti i sumirati podatke iz postojećih modula."
        ),
        examples=[Decimal("5000.00")],
    ),
    total_expense: Decimal = Query(
        0,
        ge=0,
        description=(
            "Ukupan iznos rashoda za dati period.\n\n"
            "Za početak je opciono i služi kao dodatno umanjenje osnovice. "
            "Kasnije se može povezati sa stvarnim rashodima iz cash modula."
        ),
        examples=[Decimal("1500.00")],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg radimo simulaciju mjesečnog obračuna.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
) -> MonthlyTaxSummaryRead:
    """
    Vraća **simulaciju** mjesečnog poreznog obračuna za jednog tenanta,
    koristeći DUMMY porezne stope i jednostavnu formulu.

    Trenutna logika (DUMMY, može se mijenjati po potrebi):

    1. Priznati paušalni troškovi = `total_income * flat_costs_rate`
    2. Oporeziva osnovica = `total_income - priznati_pausalni_troskovi - total_expense`
       (ako je rezultat < 0, osnovica se svodi na 0)
    3. Porez na dohodak = `oporeziva_osnovica * income_tax_rate`
    4. Doprinosi (zbirno) = `oporeziva_osnovica * (PIO + zdravstveno + nezaposlenost)`
    5. Ukupna obaveza = `porez + doprinosi`

    > **Napomena:** Ovo je razvojni model, nije pravni savjet niti tačan prikaz poreskog sistema.
    """
    tenant = _require_tenant(x_tenant_code)
    cfg = TAX_DUMMY_CONFIG

    return _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )


@router.get(
    "/tax/monthly/auto",
    response_model=MonthlyTaxSummaryRead,
    summary="Automatski mjesečni obračun iz invoices + cash (DUMMY)",
)
def auto_monthly_tax(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
        description="Godina obračuna (YYYY).",
        examples=[2025],
    ),
    month: int = Query(
        ...,
        ge=1,
        le=12,
        description="Mjesec obračuna (1-12).",
        examples=[1],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg radimo automatski mjesečni obračun.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxSummaryRead:
    """
    Automatski mjesečni porezni obračun za jednog tenanta **na osnovu podataka iz baze**.

    Trenutna DUMMY logika agregacije izvora prihoda/rashoda:

    - prihodi:
        - suma `Invoice.total_amount` za zadati mjesec (po `issue_date`)
        - PLUS suma `CashEntry.amount` za zapise sa `kind='income'`
    - rashodi:
        - suma `CashEntry.amount` za zapise sa `kind='expense'`

    Datumski opseg:
    - od prvog dana mjeseca (uključivo)
    - do prvog dana sljedećeg mjeseca (isključivo)

    > **Napomena:** Model je pojednostavljen i služi kao razvojni DUMMY obračun,
    > a ne kao pravno-validan poreski sistem.
    """
    tenant = _require_tenant(x_tenant_code)
    cfg = TAX_DUMMY_CONFIG

    month_start, month_end = _month_bounds(year, month)

    # 1) Prihodi iz faktura (Invoice.total_amount)
    stmt_invoices = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("invoice_income")
    ).where(
        Invoice.tenant_code == tenant,
        Invoice.issue_date >= month_start,
        Invoice.issue_date < month_end,
    )
    invoice_row = db.execute(stmt_invoices).one()
    invoice_income = invoice_row.invoice_income or Decimal("0.00")

    # 2) Prihodi i rashodi iz cash_entries
    income_expr = func.coalesce(
        func.sum(
            case(
                (CashEntry.kind == "income", CashEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    expense_expr = func.coalesce(
        func.sum(
            case(
                (CashEntry.kind == "expense", CashEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    stmt_cash = select(
        income_expr.label("cash_income"),
        expense_expr.label("cash_expense"),
    ).where(
        CashEntry.tenant_code == tenant,
        CashEntry.entry_date >= month_start,
        CashEntry.entry_date < month_end,
    )

    cash_row = db.execute(stmt_cash).one()
    cash_income = cash_row.cash_income or Decimal("0.00")
    cash_expense = cash_row.cash_expense or Decimal("0.00")

    # 3) Kombinacija izvora
    total_income = invoice_income + cash_income
    total_expense = cash_expense

    return _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )
