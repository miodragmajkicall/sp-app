from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path
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

    Koristi se kao početna vrijednost u sumiranju (sum(iterable, _d0())).
    """
    return Decimal("0.00")


@router.get(
    "/overview/{year}",
    response_model=SamOverviewRead,
    summary="Godišnji SAM overview (12 mjeseci + godišnji sažetak)",
    description=(
        "Vraća kombinovani SAM pregled obaveza samostalnog preduzetnika za zadanu godinu.\n\n"
        "Ovaj endpoint spaja podatke iz TAX modula (`tax_monthly_results`) u format pogodan "
        "za dashboard i grafove:\n\n"
        "- za finalizovane mjesece koristi vrijednosti iz `TaxMonthlyResult`,\n"
        "- za mjesece bez zapisa vraća početne vrijednosti 0.00 i `is_finalized = false`,\n"
        "- uvijek vraća tačno 12 elemenata u listi `months`.\n\n"
        "Na ovaj način UI dobija stabilan shape (uvijek 12 mjeseci) i tačne podatke za zaključane mjesece.\n"
        "Kasnije se endpoint može proširiti integracijom sa preview obračunom za otvorene mjesece."
    ),
    operation_id="sam_overview",
    responses={
        200: {
            "description": "Uspješan SAM overview za zadanu godinu i tenanta.",
            "content": {
                "application/json": {
                    "example": {
                        "tenant_code": "t-demo",
                        "year": 2025,
                        "months": [
                            {
                                "month": 1,
                                "month_label": "01.2025",
                                "income_total": "5000.00",
                                "expense_total": "1500.00",
                                "tax_base": "2000.00",
                                "tax_due": "200.00",
                                "contributions_due": "520.00",
                                "total_due": "720.00",
                                "is_finalized": True,
                            },
                            {
                                "month": 2,
                                "month_label": "02.2025",
                                "income_total": "0.00",
                                "expense_total": "0.00",
                                "tax_base": "0.00",
                                "tax_due": "0.00",
                                "contributions_due": "0.00",
                                "total_due": "0.00",
                                "is_finalized": False,
                            },
                        ],
                        "yearly_summary": {
                            "year": 2025,
                            "income_total": "5000.00",
                            "expense_total": "1500.00",
                            "tax_base_total": "2000.00",
                            "tax_due_total": "200.00",
                            "contributions_due_total": "520.00",
                            "total_due": "720.00",
                            "finalized_months": 1,
                            "open_months": 11,
                        },
                    }
                }
            },
        },
        400: {
            "description": (
                "Greška u zahtjevu.\n\n"
                "Tipični scenariji:\n"
                "- nedostaje `X-Tenant-Code` header → `Missing X-Tenant-Code header`\n"
                "- godina je van dozvoljenog opsega 2000–2100."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "missing_tenant": {
                            "summary": "Nedostaje X-Tenant-Code",
                            "value": {"detail": "Missing X-Tenant-Code header"},
                        },
                        "invalid_year": {
                            "summary": "Godina van dozvoljenog opsega",
                            "value": {
                                "detail": "Godina mora biti u rasponu 2000–2100."
                            },
                        },
                    }
                }
            },
        },
    },
)
def get_sam_overview(
    year: int = Path(
        ...,
        description="Godina SAM pregleda (YYYY). Dozvoljeni opseg: 2000–2100.",
        examples=[2025],
    ),
    tenant_code: str = Depends(_require_tenant),
    db: Session = Depends(_get_session_dep),
) -> SamOverviewRead:
    """
    SAM overview spojen na TAX modul (`tax_monthly_results`).

    Koraci:

    1. Validira se raspon godine (2000–2100). Ako je godina van opsega → HTTP 400.
    2. Učitavaju se svi `TaxMonthlyResult` zapisi za (tenant_code, year).
    3. Za svaki mjesec 1-12:
        - ako postoji zapis u bazi → vrijednosti se pune iz `TaxMonthlyResult`,
        - ako ne postoji → koristi se 0.00 za sve iznose i `is_finalized=False`.
    4. Izračunava se godišnji sažetak (`SamYearlySummary`) kao suma iznosa po mjesecima,
       uz broj finalizovanih i otvorenih mjeseci.

    Ovaj endpoint je idealan za:

    - godišnji graf prihoda/rashoda,
    - listu mjeseci sa statusom (zaključan / otvoren),
    - brzu kontrolnu tablu za SP korisnika.
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
