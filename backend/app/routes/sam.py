from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import TaxMonthlyResult
from app.schemas.sam import SamMonthlyItem, SamOverviewRead, SamYearlySummary
from app.tenant_security import require_tenant_code

router = APIRouter(
    prefix="/sam",
    tags=["sam"],
)


def _require_tenant(
    x_tenant_code: Optional[str] = Header(
        default=None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg čitamo SAM overview.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
) -> str:
    """
    Minimalna validacija tenanta za SAM.

    Sve se radi u kontekstu jednog tenanta:
    - header X-Tenant-Code je obavezan.

    Implementacija delegira na shared helper `require_tenant_code` kako bi
    poruka o grešci bila konzistentna sa ostatkom sistema:
    - `Missing X-Tenant-Code header`.
    """
    return require_tenant_code(x_tenant_code)


def _d0() -> Decimal:
    """
    Helper za Decimal(0.00) sa 2 decimale.
    """
    return Decimal("0.00")


def _build_sam_overview(
    *,
    year: int,
    tenant_code: str,
    db: Session,
) -> SamOverviewRead:
    """
    Interna helper funkcija koja gradi SAM overview za zadatu godinu/tenanta.

    Koriste je i:
    - GET /sam/overview/{year} (JSON)
    - GET /sam/overview/{year}/export (CSV)

    Tako osiguravamo da oba endpoint-a imaju identičnu logiku.
    """
    if year < 2000 or year > 2100:
        raise HTTPException(
            status_code=400,
            detail="Godina mora biti u rasponu 2000–2100.",
        )

    # 1) Učitavamo sve mjesečne rezultate za datog tenanta i godinu
    results: List[TaxMonthlyResult] = (
        db.query(TaxMonthlyResult)
        .filter(
            TaxMonthlyResult.tenant_code == tenant_code,
            TaxMonthlyResult.year == year,
        )
        .all()
    )

    results_by_month: dict[int, TaxMonthlyResult] = {r.month: r for r in results}

    months: List[SamMonthlyItem] = []

    # 2) Generišemo 12 mjeseci, kombinujemo realne rezultate + default
    for m in range(1, 13):
        month_label = f"{m:02d}.{year}"
        result = results_by_month.get(m)

        if result is not None:
            # Realni podaci iz tax_monthly_results
            item = SamMonthlyItem(
                month=m,
                month_label=month_label,
                income_total=result.total_income,
                expense_total=result.total_expense,
                tax_base=result.taxable_base,
                tax_due=result.income_tax,
                contributions_due=result.contributions_total,
                total_due=result.total_due,
                is_finalized=bool(result.is_final),
            )
        else:
            # Nema obračuna za ovaj mjesec → početne vrijednosti
            item = SamMonthlyItem(
                month=m,
                month_label=month_label,
                income_total=_d0(),
                expense_total=_d0(),
                tax_base=_d0(),
                tax_due=_d0(),
                contributions_due=_d0(),
                total_due=_d0(),
                is_finalized=False,
            )

        months.append(item)

    # 3) Godišnji sažetak kao suma svih 12 mjeseci
    income_total = sum((m.income_total for m in months), _d0())
    expense_total = sum((m.expense_total for m in months), _d0())
    tax_base_total = sum((m.tax_base for m in months), _d0())
    tax_due_total = sum((m.tax_due for m in months), _d0())
    contributions_due_total = sum((m.contributions_due for m in months), _d0())
    total_due = sum((m.total_due for m in months), _d0())

    finalized_months = sum(1 for m in months if m.is_finalized)
    open_months = 12 - finalized_months

    yearly_summary = SamYearlySummary(
        year=year,
        income_total=income_total,
        expense_total=expense_total,
        tax_base_total=tax_base_total,
        tax_due_total=tax_due_total,
        contributions_due_total=contributions_due_total,
        total_due=total_due,
        finalized_months=finalized_months,
        open_months=open_months,
    )

    return SamOverviewRead(
        tenant_code=tenant_code,
        year=year,
        months=months,
        yearly_summary=yearly_summary,
    )


@router.get(
    "/overview/{year}",
    response_model=SamOverviewRead,
    summary="Godišnji SAM overview (kombinovani monthly + yearly odgovor).",
    description=(
        "Vraća kombinovani SAM pregled obaveza samostalnog preduzetnika za zadanu godinu.\n\n"
        "Ova verzija endpointa koristi **realne podatke iz tax_monthly_results** gdje postoje:\n"
        "- za finalizovane mjesece koristi vrijednosti iz `TaxMonthlyResult`,\n"
        "- za mjesece bez zapisa vraća početne vrijednosti 0.00 i `is_finalized = false`.\n\n"
        "Na ovaj način UI dobija stabilan shape (uvijek 12 mjeseci) i tačne podatke za zaključane mjesece.\n"
        "Kasnije se može nadograditi i integracijom sa preview obračunom za otvorene mjesece."
    ),
)
def get_sam_overview(
    year: int,
    tenant_code: str = Depends(_require_tenant),
    db: Session = Depends(_get_session_dep),
) -> SamOverviewRead:
    """
    SAM overview spojen na TAX modul (tax_monthly_results).

    - validira raspon godine,
    - čita sve `TaxMonthlyResult` za (tenant_code, year),
    - za svaki mjesec 1-12:
        - ako postoji zapis u bazi → puni se iz realnih vrijednosti,
        - ako ne postoji → puni se sa 0.00 i `is_finalized=False`,
    - računa godišnji sažetak (suma svih 12 mjeseci).
    """
    return _build_sam_overview(year=year, tenant_code=tenant_code, db=db)


@router.get(
    "/overview/{year}/export",
    summary="Export SAM overview pregleda u CSV format",
    description=(
        "Exportuje kompletan SAM overview za zadatu godinu i tenant-a u CSV fajl.\n\n"
        "Struktura CSV-a:\n"
        "1) Sekcija 'months' – 12 redova (po mjesecu):\n"
        "   columns: section,month,month_label,income_total,expense_total,"
        "tax_base,tax_due,contributions_due,total_due,is_finalized\n\n"
        "2) Prazan red\n\n"
        "3) Sekcija 'yearly' – jedan red sa godišnjim sažetkom:\n"
        "   columns: section,year,income_total,expense_total,tax_base_total,"
        "tax_due_total,contributions_due_total,total_due,finalized_months,open_months\n\n"
        "CSV je pogodan za uvoz u Excel ili dalje knjigovodstvene alate."
    ),
)
def export_sam_overview_csv(
    year: int,
    tenant_code: str = Depends(_require_tenant),
    db: Session = Depends(_get_session_dep),
) -> Response:
    """
    CSV export SAM overview-a za zadatu godinu i tenant-a.

    Koristi istu internu logiku kao i JSON endpoint, preko `_build_sam_overview`,
    tako da su podaci uvijek 1:1 usklađeni.
    """
    overview = _build_sam_overview(year=year, tenant_code=tenant_code, db=db)

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    # 1) Monthly sekcija
    writer.writerow(
        [
            "section",
            "month",
            "month_label",
            "income_total",
            "expense_total",
            "tax_base",
            "tax_due",
            "contributions_due",
            "total_due",
            "is_finalized",
        ]
    )

    for m in overview.months:
        writer.writerow(
            [
                "month",
                m.month,
                m.month_label,
                str(m.income_total),
                str(m.expense_total),
                str(m.tax_base),
                str(m.tax_due),
                str(m.contributions_due),
                str(m.total_due),
                "true" if m.is_finalized else "false",
            ]
        )

    # Prazan red kao separator
    writer.writerow([])

    # 2) Yearly sekcija
    ys = overview.yearly_summary
    writer.writerow(
        [
            "section",
            "year",
            "income_total",
            "expense_total",
            "tax_base_total",
            "tax_due_total",
            "contributions_due_total",
            "total_due",
            "finalized_months",
            "open_months",
        ]
    )
    writer.writerow(
        [
            "yearly",
            ys.year,
            str(ys.income_total),
            str(ys.expense_total),
            str(ys.tax_base_total),
            str(ys.tax_due_total),
            str(ys.contributions_due_total),
            str(ys.total_due),
            ys.finalized_months,
            ys.open_months,
        ]
    )

    csv_content = buffer.getvalue()
    buffer.close()

    filename = f"sam-overview-{tenant_code}-{year}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
