from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Invoice, TaxMonthlyResult
from app.tenant_security import require_tenant_code, ensure_tenant_exists
from app.schemas.dashboard import (
    DashboardCashSummary,
    DashboardInvoiceSummary,
    DashboardTaxSummary,
    DashboardYearSummary,
    DashboardSamSummary,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Shared helper za čitanje i validaciju X-Tenant-Code header-a.
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Osigurava da tenant postoji u bazi (radi konzistentnosti
    sa ostatkom sistema).
    """
    ensure_tenant_exists(db, code)


@router.get(
    "/summary/{year}",
    response_model=DashboardYearSummary,
    summary="Godišnji dashboard sa ključnim brojkama",
    description=(
        "Vraća kombinovani sažetak za jednog tenanta i zadatu godinu:\n\n"
        "- **cash**: ukupni prihodi, rashodi i neto cashflow (iz `cash_entries`),\n"
        "- **invoices**: broj izlaznih faktura i njihov ukupni iznos (iz `invoices`),\n"
        "- **tax**: broj obračunatih mjeseci i ukupna obaveza prema državi "
        "(iz `tax_monthly_results`),\n"
        "- **sam**: pojednostavljen SAM sažetak (godišnja obaveza + flag da li "
        "postoje obračuni).\n\n"
        "Ovo je osnovni endpoint za početni ekran (dashboard) u UI-ju."
    ),
)
def get_dashboard_year_summary(
    year: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta za kojeg se generiše dashboard.",
    ),
) -> DashboardYearSummary:
    """
    Kombinuje više modula u jedan yearly dashboard response.
    """
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

    # ============================
    #  CASH SUMMARY
    # ============================
    income_sum = (
        db.query(func.coalesce(func.sum(CashEntry.amount), 0))
        .filter(
            CashEntry.tenant_code == tenant,
            CashEntry.kind == "income",
            func.extract("year", CashEntry.entry_date) == year,
        )
        .scalar()
    )
    expense_sum = (
        db.query(func.coalesce(func.sum(CashEntry.amount), 0))
        .filter(
            CashEntry.tenant_code == tenant,
            CashEntry.kind == "expense",
            func.extract("year", CashEntry.entry_date) == year,
        )
        .scalar()
    )

    income_total = Decimal(income_sum or 0)
    expense_total = Decimal(expense_sum or 0)
    net_cashflow = income_total - expense_total

    cash_summary = DashboardCashSummary(
        year=year,
        income_total=income_total,
        expense_total=expense_total,
        net_cashflow=net_cashflow,
    )

    # ============================
    #  INVOICES SUMMARY
    # ============================
    invoices_query = db.query(
        func.count(Invoice.id),
        func.coalesce(func.sum(Invoice.total_amount), 0),
    ).filter(
        Invoice.tenant_code == tenant,
        func.extract("year", Invoice.issue_date) == year,
    )

    invoices_count_raw, invoices_total_raw = invoices_query.one()
    invoices_count = int(invoices_count_raw or 0)
    invoices_total = Decimal(invoices_total_raw or 0)

    invoices_summary = DashboardInvoiceSummary(
        year=year,
        invoices_count=invoices_count,
        total_amount=invoices_total,
    )

    # ============================
    #  TAX SUMMARY
    # ============================
    tax_query = db.query(
        func.count(TaxMonthlyResult.id),
        func.coalesce(func.sum(TaxMonthlyResult.total_due), 0),
    ).filter(
        TaxMonthlyResult.tenant_code == tenant,
        TaxMonthlyResult.year == year,
    )

    finalized_months_raw, tax_total_due_raw = tax_query.one()
    finalized_months = int(finalized_months_raw or 0)
    tax_total_due = Decimal(tax_total_due_raw or 0)

    tax_summary = DashboardTaxSummary(
        year=year,
        finalized_months=finalized_months,
        total_due=tax_total_due,
    )

    # ============================
    #  SAM SUMMARY (lightweight bridge ka SAM modulu)
    # ============================
    sam_summary = DashboardSamSummary(
        year=year,
        yearly_total_due=tax_total_due,
        has_any_finalized=finalized_months > 0,
    )

    # ============================
    #  FINAL RESPONSE
    # ============================
    return DashboardYearSummary(
        tenant_code=tenant,
        year=year,
        cash=cash_summary,
        invoices=invoices_summary,
        tax=tax_summary,
        sam=sam_summary,
    )
