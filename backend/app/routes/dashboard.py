from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
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
    DashboardMonthlySummary,
    DashboardMonthlyCashSummary,
    DashboardMonthlyInvoiceSummary,
    DashboardMonthlyTaxSummary,
    DashboardMonthlySamSummary,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Shared helper za čitanje i validaciju X-Tenant-Code header-a.

    Delegira na globalni require_tenant_code tako da je poruka konzistentna:
    - ako header nedostaje → 400 + "Missing X-Tenant-Code header"
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists_wrapper(db: Session, code: str) -> None:
    """
    Osigurava da tenant postoji u bazi (radi konzistentnosti
    sa ostatkom sistema).
    """
    ensure_tenant_exists(db, code)


# ======================================================
#  GODIŠNJI DASHBOARD
# ======================================================
@router.get(
    "/summary/{year}",
    response_model=DashboardYearSummary,
    summary="Godišnji dashboard sa ključnim brojkama",
    description=(
        "Vraća kombinovani sažetak za jednog tenenta i zadatu godinu:\n\n"
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
    _ensure_tenant_exists_wrapper(db, tenant)

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


# ======================================================
#  MJESNIČNI DASHBOARD – HELPER
# ======================================================
def _compute_monthly_dashboard(
    *,
    db: Session,
    tenant: str,
    year: int,
    month: int,
) -> DashboardMonthlySummary:
    """
    Centralno mjesto za mjesečni dashboard:

    - cash agregacija za (year, month),
    - invoices agregacija za (year, month),
    - tax_monthly_results za (year, month),
    - SAM mjesečni sažetak.
    """

    # ----------------------------
    # CASH (income / expense / net)
    # ----------------------------
    income_sum = (
        db.query(func.coalesce(func.sum(CashEntry.amount), 0))
        .filter(
            CashEntry.tenant_code == tenant,
            CashEntry.kind == "income",
            func.extract("year", CashEntry.entry_date) == year,
            func.extract("month", CashEntry.entry_date) == month,
        )
        .scalar()
    )
    expense_sum = (
        db.query(func.coalesce(func.sum(CashEntry.amount), 0))
        .filter(
            CashEntry.tenant_code == tenant,
            CashEntry.kind == "expense",
            func.extract("year", CashEntry.entry_date) == year,
            func.extract("month", CashEntry.entry_date) == month,
        )
        .scalar()
    )

    income_total = Decimal(income_sum or 0)
    expense_total = Decimal(expense_sum or 0)
    net_cashflow = income_total - expense_total

    cash_summary = DashboardMonthlyCashSummary(
        year=year,
        month=month,
        income_total=income_total,
        expense_total=expense_total,
        net_cashflow=net_cashflow,
    )

    # ----------------------------
    # INVOICES (count + total)
    # ----------------------------
    invoices_query = db.query(
        func.count(Invoice.id),
        func.coalesce(func.sum(Invoice.total_amount), 0),
    ).filter(
        Invoice.tenant_code == tenant,
        func.extract("year", Invoice.issue_date) == year,
        func.extract("month", Invoice.issue_date) == month,
    )

    invoices_count_raw, invoices_total_raw = invoices_query.one()
    invoices_count = int(invoices_count_raw or 0)
    invoices_total = Decimal(invoices_total_raw or 0)

    invoices_summary = DashboardMonthlyInvoiceSummary(
        year=year,
        month=month,
        invoices_count=invoices_count,
        total_amount=invoices_total,
    )

    # ----------------------------
    # TAX (tax_monthly_results)
    # ----------------------------
    tax_rows: list[TaxMonthlyResult] = (
        db.query(TaxMonthlyResult)
        .filter(
            TaxMonthlyResult.tenant_code == tenant,
            TaxMonthlyResult.year == year,
            TaxMonthlyResult.month == month,
        )
        .all()
    )

    has_any_result = len(tax_rows) > 0
    total_due = sum((row.total_due for row in tax_rows), Decimal("0.00"))
    is_any_final = any(bool(row.is_final) for row in tax_rows)

    tax_summary = DashboardMonthlyTaxSummary(
        year=year,
        month=month,
        has_result=has_any_result,
        is_final=is_any_final,
        total_due=total_due,
    )

    # ----------------------------
    # SAM (lightweight monthly view)
    # ----------------------------
    sam_summary = DashboardMonthlySamSummary(
        year=year,
        month=month,
        total_due=total_due,
        has_result=has_any_result,
        is_final=is_any_final,
    )

    return DashboardMonthlySummary(
        tenant_code=tenant,
        year=year,
        month=month,
        cash=cash_summary,
        invoices=invoices_summary,
        tax=tax_summary,
        sam=sam_summary,
    )


# ======================================================
#  MJESNIČNI DASHBOARD – /monthly/{year}/{month}
# ======================================================
@router.get(
    "/monthly/{year}/{month}",
    response_model=DashboardMonthlySummary,
    summary="Mjesečni dashboard za zadanu godinu i mjesec",
    description=(
        "Vraća kombinovani mjesečni sažetak (cash + fakture + tax + SAM) za jednog "
        "tenanta i konkretan (year, month) par.\n\n"
        "Tipično se koristi kada korisnik u UI-ju mijenja mjesec u nekom dropdownu "
        "ili kalendaru."
    ),
)
def get_dashboard_monthly_summary(
    year: int,
    month: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta za kojeg se generiše mjesečni dashboard.",
    ),
) -> DashboardMonthlySummary:
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists_wrapper(db, tenant)

    if year < 2000 or year > 2100:
        raise HTTPException(
            status_code=400,
            detail="Year must be between 2000 and 2100.",
        )
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12.",
        )

    return _compute_monthly_dashboard(
        db=db,
        tenant=tenant,
        year=year,
        month=month,
    )


# ======================================================
#  MJESNIČNI DASHBOARD – /monthly/current
# ======================================================
@router.get(
    "/monthly/current",
    response_model=DashboardMonthlySummary,
    summary="Mjesečni dashboard za trenutni mjesec (ili ručno zadat preko query parametara)",
    description=(
        "Vraća mjesečni dashboard za **trenutni mjesec na serveru**, ili za godinu/mjesec "
        "koji se eksplicitno pošalju kao query parametri `year` i `month`.\n\n"
        "Ako se year i month izostave → koristi se današnji datum (date.today()).\n"
        "Ako se pošalje samo jedan od parametara → vraća 400 (oboje ili nijedan)."
    ),
)
def get_dashboard_monthly_current(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta za kojeg se generiše mjesečni dashboard.",
    ),
    year: Optional[int] = Query(
        None,
        ge=2000,
        le=2100,
        description="Opcioni override godine (YYYY). Ako je zadat, mora i month.",
    ),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Opcioni override mjeseca (1-12). Ako je zadat, mora i year.",
    ),
) -> DashboardMonthlySummary:
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists_wrapper(db, tenant)

    # Ili oba None, ili oba popunjena.
    if (year is None) ^ (month is None):
        raise HTTPException(
            status_code=400,
            detail="Both year and month must be provided together or omitted.",
        )

    if year is None and month is None:
        today = date.today()
        year = today.year
        month = today.month

    assert year is not None and month is not None  # za type-checkere

    return _compute_monthly_dashboard(
        db=db,
        tenant=tenant,
        year=year,
        month=month,
    )
