from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import TaxMonthlyResult, TaxYearlyResult
from app.schemas.sam import SamOverviewRead, SamMonthlyItemRead
from app.tenant_security import require_tenant_code

router = APIRouter(
    prefix="/sam",
    tags=["sam"],
)


@router.get(
    "/overview",
    response_model=SamOverviewRead,
    summary="Godišnji SAM pregled obaveza prema državi",
    description=(
        "Vraća godišnji SAM pregled obaveza za jednog tenenta (SP).\n\n"
        "Backend koristi već izračunate podatke iz poreskog modula "
        "(`tax_monthly_results` i `tax_yearly_results`) i iz njih pravi "
        "sažetak za UI:\n\n"
        "- po mjesecima: koliko treba uplatiti državi (porez + doprinosi) i da li je mjesec finalizovan\n"
        "- godišnji zbir: ukupna obaveza za cijelu godinu\n\n"
        "Ako postoji godišnji zapis u `tax_yearly_results`, njegov `total_due` "
        "se koristi kao referentna godišnja obaveza. Ako ne postoji, koristi se zbir "
        "svih `total_due` vrijednosti iz finalizovanih mjeseci."
    ),
    operation_id="sam_overview_year",
)
def sam_overview(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se računa SAM pregled (YYYY).",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta (SP) za kojeg se traži pregled. Primjer: `frizer-mika`, `t-demo`.",
    ),
    db: Session = Depends(_get_session_dep),
) -> SamOverviewRead:
    """
    SAM pregled obaveza za jednog tenenta (SP) za zadatu godinu.

    Implementacija:
    1. Validira i pročita `tenant_code` iz `X-Tenant-Code` headera.
    2. Učita sve mjesečne rezultate iz `tax_monthly_results` za (tenant_code, year).
    3. Od njih napravi listu `SamMonthlyItemRead` (month, is_final, total_due).
    4. Ako postoji godišnji zapis u `tax_yearly_results`, koristi njegov `total_due`
       kao `yearly_total_due`. Ako ne, sabira `total_due` svih finalizovanih mjeseci.
    """
    tenant = require_tenant_code(x_tenant_code)

    # 1) Učitavanje mjesečnih rezultata za godinu
    monthly_rows: List[TaxMonthlyResult] = (
        db.execute(
            select(TaxMonthlyResult).where(
                TaxMonthlyResult.tenant_code == tenant,
                TaxMonthlyResult.year == year,
            )
        )
        .scalars()
        .all()
    )

    monthly_items: list[SamMonthlyItemRead] = []
    yearly_total_due = Decimal("0.00")
    currency = "BAM"

    if monthly_rows:
        currency = monthly_rows[0].currency or "BAM"

    for row in monthly_rows:
        monthly_items.append(
            SamMonthlyItemRead(
                year=row.year,
                month=row.month,
                is_final=bool(row.is_final),
                total_due=row.total_due,
            )
        )
        # Za zbir uzimamo samo finalizovane mjesece
        if row.is_final:
            yearly_total_due += row.total_due

    # 2) Ako postoji godišnji rezultat, koristimo njega kao izvor istine
    yearly_row: Optional[TaxYearlyResult] = (
        db.execute(
            select(TaxYearlyResult).where(
                TaxYearlyResult.tenant_code == tenant,
                TaxYearlyResult.year == year,
            )
        )
        .scalars()
        .first()
    )

    if yearly_row is not None:
        yearly_total_due = yearly_row.total_due
        currency = yearly_row.currency or currency

    return SamOverviewRead(
        tenant_code=tenant,
        year=year,
        monthly=monthly_items,
        yearly_total_due=yearly_total_due,
        currency=currency,
    )
