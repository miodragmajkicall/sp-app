# /home/miso/dev/sp-app/sp-app/backend/app/routes/reports.py
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
import csv
import io

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.tenant_security import require_tenant_code
from app.routes.tax import _aggregate_monthly_income_and_expense, yearly_tax_preview

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


# ======================================================
#  TENANT HELPER
# ======================================================
def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Osigurava da je `X-Tenant-Code` header postavljen, delegira na shared helper.

    - Ako nedostaje ili je prazan → baca HTTP 400 sa porukom
      `Missing X-Tenant-Code header`.
    - Ako je postavljen → vraća vrijednost header-a kao string.
    """
    return require_tenant_code(x_tenant_code)


# ======================================================
#  SCHEMAS (lokalne za reports modul)
# ======================================================
class CashflowMonthlyItem(BaseModel):
    month: int
    income: Decimal
    expense: Decimal
    profit: Decimal
    currency: str = "BAM"


class CashflowYearResponse(BaseModel):
    year: int
    tenant_code: str
    items: List[CashflowMonthlyItem]


class YearSummaryResponse(BaseModel):
    year: int
    tenant_code: str
    total_income: Decimal
    total_expense: Decimal
    profit: Decimal
    taxable_base: Decimal
    income_tax: Decimal
    contributions_total: Decimal
    total_due: Decimal
    currency: str = "BAM"


# ======================================================
#  CASHFLOW – GODIŠNJI PREGLED PO MJESECIMA (JSON)
# ======================================================
@router.get(
    "/cashflow/{year}",
    response_model=CashflowYearResponse,
    summary="Godišnji cashflow (prihodi/rashodi/profit po mjesecima)",
    description=(
        "Vraća godišnji **cashflow overview** za jednog tenenta, grupisano po mjesecima.\n\n"
        "Za svaki mjesec (1–12) računa:\n"
        "- `income`  → prihodi iz invoices + cash_entries (kind='income')\n"
        "- `expense` → rashodi iz cash_entries (kind='expense') + input_invoices\n"
        "- `profit`  → `income - expense`\n\n"
        "Podaci se računaju korištenjem iste agregacione logike kao i TAX modul "
        "(`_aggregate_monthly_income_and_expense`).\n\n"
        "Ovaj endpoint je idealan za grafički prikaz u UI-ju (npr. bar/line chart "
        "sa 12 tačaka za godinu).\n\n"
        "Primjer poziva:\n"
        "`GET /reports/cashflow/2025` sa headerom `X-Tenant-Code: t-demo`."
    ),
    operation_id="reports_cashflow_year",
)
def get_cashflow_year(
    year: int = Path(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se računa cashflow overview.",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenenta za kojeg se računa cashflow overview.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> CashflowYearResponse:
    """
    Godišnji cashflow overview po mjesecima.

    Za svaki mjesec od 1 do 12 internim pozivom koristi
    `_aggregate_monthly_income_and_expense` iz TAX modula kako bi dobio
    ukupne prihode i rashode za taj mjesec, a zatim računa profit:

    `profit = income - expense`.

    Rezultat je stabilan, koristi iste izvore podataka kao i TAX mjesečni obračun:
    - invoices
    - cash_entries
    - input_invoices
    """
    tenant = _require_tenant(x_tenant_code)

    items: list[CashflowMonthlyItem] = []

    for month in range(1, 13):
        total_income, total_expense = _aggregate_monthly_income_and_expense(
            year=year,
            month=month,
            tenant_code=tenant,
            db=db,
        )
        profit = total_income - total_expense

        items.append(
            CashflowMonthlyItem(
                month=month,
                income=total_income,
                expense=total_expense,
                profit=profit,
                currency="BAM",
            )
        )

    return CashflowYearResponse(
        year=year,
        tenant_code=tenant,
        items=items,
    )


# ======================================================
#  CASHFLOW – CSV EXPORT
# ======================================================
@router.get(
    "/cashflow/{year}/export",
    summary="Godišnji cashflow export u CSV",
    description=(
        "Exportuje godišnji cashflow overview u CSV format.\n\n"
        "CSV sadrži header + po jedan red za svaki mjesec (1–12):\n"
        "columns: year,month,tenant_code,income,expense,profit,currency\n\n"
        "Primjer poziva:\n"
        "`GET /reports/cashflow/2025/export` sa headerom `X-Tenant-Code: t-demo`."
    ),
    operation_id="reports_cashflow_year_export",
)
def export_cashflow_year_csv(
    year: int = Path(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se exportuje cashflow overview.",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenenta za kojeg se exportuje cashflow overview.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> Response:
    """
    CSV export godišnjeg cashflow overview-a.

    Interno koristi istu logiku kao `get_cashflow_year`, ali rezultat serializuje
    u CSV sa 13 redova (header + 12 mjeseci).
    """
    tenant = _require_tenant(x_tenant_code)

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    # Header
    writer.writerow(
        ["year", "month", "tenant_code", "income", "expense", "profit", "currency"]
    )

    # 12 mjeseci
    for month in range(1, 13):
        total_income, total_expense = _aggregate_monthly_income_and_expense(
            year=year,
            month=month,
            tenant_code=tenant,
            db=db,
        )
        profit = total_income - total_expense

        writer.writerow(
            [
                year,
                month,
                tenant,
                str(total_income),
                str(total_expense),
                str(profit),
                "BAM",
            ]
        )

    csv_content = buffer.getvalue()
    buffer.close()

    filename = f"cashflow-{tenant}-{year}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ======================================================
#  GODIŠNJI SUMMARY – COMBO (CASH + TAX)
# ======================================================
@router.get(
    "/year-summary/{year}",
    response_model=YearSummaryResponse,
    summary="Godišnji summary (cashflow + porezi) za tenenta",
    description=(
        "Vraća **godišnji summary** za jednog tenenta:\n"
        "- zbirni prihodi, rashodi i profit (sumirano kroz mjesece)\n"
        "- godišnji porez i doprinosi iz TAX modula (logika `yearly_tax_preview`)\n\n"
        "Ovo je idealan endpoint za godišnji dashboard/presek.\n\n"
        "Primjer poziva:\n"
        "`GET /reports/year-summary/2025` sa headerom `X-Tenant-Code: t-demo`."
    ),
    operation_id="reports_year_summary",
)
def get_year_summary(
    year: int = Path(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se računa godišnji summary.",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenenta za kojeg se računa godišnji summary.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> YearSummaryResponse:
    """
    Kombinovani godišnji summary za jednog tenenta.

    - Zbirni prihodi/rashodi/profit za sve mjesece (1–12) koristeći istu
      agregaciju kao TAX modul.
    - Porez i doprinosi iz `yearly_tax_preview` (sabira već finalizovane mjesece).

    Ako nema finalizovanih mjeseci, porezni dio će biti 0 (DUMMY logika kao u TAX).
    """
    tenant = _require_tenant(x_tenant_code)

    # 1) Sabiranje prihoda/rashoda preko 12 mjeseci
    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")

    for month in range(1, 13):
        income, expense = _aggregate_monthly_income_and_expense(
            year=year,
            month=month,
            tenant_code=tenant,
            db=db,
        )
        total_income += income
        total_expense += expense

    profit = total_income - total_expense

    # 2) Poreski dio – reuse yearly_tax_preview
    yearly_tax = yearly_tax_preview(
        year=year,
        x_tenant_code=tenant,
        db=db,
    )

    return YearSummaryResponse(
        year=year,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        profit=profit,
        taxable_base=yearly_tax.taxable_base,
        income_tax=yearly_tax.income_tax,
        contributions_total=yearly_tax.contributions_total,
        total_due=yearly_tax.total_due,
        currency=yearly_tax.currency,
    )
