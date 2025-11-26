from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Invoice, TaxMonthlyResult
from app.schemas.tax import (
    ErrorResponse,
    MonthlyTaxStatusResponse,
    MonthlyTaxSummaryRead,
    TaxDummyConfig,
    YearlyTaxSummaryRead,
)

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


def _aggregate_monthly_income_and_expense(
    *,
    year: int,
    month: int,
    tenant_code: str,
    db: Session,
) -> Tuple[Decimal, Decimal]:
    """
    Agregira prihode i rashode za zadati mjesec iz:
    - invoices (total_amount)
    - cash_entries (income/expense)
    """
    month_start, month_end = _month_bounds(year, month)

    # 1) Prihodi iz faktura (Invoice.total_amount)
    stmt_invoices = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("invoice_income")
    ).where(
        Invoice.tenant_code == tenant_code,
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
        CashEntry.tenant_code == tenant_code,
        CashEntry.entry_date >= month_start,
        CashEntry.entry_date < month_end,
    )

    cash_row = db.execute(stmt_cash).one()
    cash_income = cash_row.cash_income or Decimal("0.00")
    cash_expense = cash_row.cash_expense or Decimal("0.00")

    # Kombinacija izvora
    total_income = invoice_income + cash_income
    total_expense = cash_expense

    return total_income, total_expense


@router.get(
    "/tax/monthly/preview",
    response_model=MonthlyTaxSummaryRead,
    summary="Preview mjesečnog poreznog obračuna (ručni unos)",
    description=(
        "Vraća **simulaciju** mjesečnog poreznog obračuna za jednog tenanta na osnovu "
        "ručno proslijeđenih ukupnih prihoda i rashoda za dati mjesec.\n\n"
        "Tipični use-case: frontend već ima sumirane podatke (npr. iz izvještaja) "
        "i želi da prikaže brzi preview poreza i doprinosa prije finalizacije.\n\n"
        "Primjer poziva:\n"
        "`GET /tax/monthly/preview?year=2025&month=1&total_income=5000&total_expense=1500` "
        "sa headerom `X-Tenant-Code: t-demo`."
    ),
    responses={
        200: {
            "description": "Uspješna simulacija mjesečnog poreznog obračuna.",
            "content": {
                "application/json": {
                    "example": {
                        "year": 2025,
                        "month": 1,
                        "tenant_code": "t-demo",
                        "total_income": "5000.00",
                        "total_expense": "1500.00",
                        "taxable_base": "2000.00",
                        "income_tax": "200.00",
                        "contributions_total": "520.00",
                        "total_due": "720.00",
                        "is_final": False,
                        "currency": "BAM",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
        },
        422: {
            "description": (
                "Validation error – npr. godina/mjesec van opsega ili pogrešan format "
                "brojeva u query parametrima."
            )
        },
    },
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
    description=(
        "Automatski mjesečni porezni obračun za jednog tenanta na osnovu podataka "
        "iz baze (`invoices` + `cash_entries`).\n\n"
        "Ako već postoji finalizovan rezultat u `tax_monthly_results`, vraća se "
        "persistirani obračun umjesto novog preračuna.\n\n"
        "Primjer poziva:\n"
        "`GET /tax/monthly/auto?year=2025&month=1` "
        "sa headerom `X-Tenant-Code: t-demo`."
    ),
    responses={
        200: {
            "description": (
                "Uspješan automatski obračun ili vraćen već finalizovan rezultat "
                "za zadati mjesec."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "year": 2025,
                        "month": 1,
                        "tenant_code": "t-demo",
                        "total_income": "5000.00",
                        "total_expense": "1500.00",
                        "taxable_base": "2000.00",
                        "income_tax": "200.00",
                        "contributions_total": "520.00",
                        "total_due": "720.00",
                        "is_final": True,
                        "currency": "BAM",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
        },
        422: {
            "description": (
                "Validation error – npr. godina/mjesec van opsega ili pogrešan format "
                "query parametara."
            )
        },
    },
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

    Ako je mjesec već finalizovan (postoji zapis u tax_monthly_results),
    vraća se **persistirani rezultat** umjesto ponovnog preračuna.

    > **Napomena:** Model je pojednostavljen i služi kao razvojni DUMMY obračun,
    > a ne kao pravno-validan poreski sistem.
    """
    tenant = _require_tenant(x_tenant_code)
    cfg = TAX_DUMMY_CONFIG

    # 0) Ako postoji već finalizovan obračun, vraćamo njega.
    existing = db.execute(
        select(TaxMonthlyResult).where(
            TaxMonthlyResult.tenant_code == tenant,
            TaxMonthlyResult.year == year,
            TaxMonthlyResult.month == month,
        )
    ).scalar_one_or_none()

    if existing is not None:
        return MonthlyTaxSummaryRead(
            year=existing.year,
            month=existing.month,
            tenant_code=existing.tenant_code,
            total_income=existing.total_income,
            total_expense=existing.total_expense,
            taxable_base=existing.taxable_base,
            income_tax=existing.income_tax,
            contributions_total=existing.contributions_total,
            total_due=existing.total_due,
            is_final=existing.is_final,
            currency=existing.currency,
        )

    # 1) Agregacija iz invoices + cash_entries
    total_income, total_expense = _aggregate_monthly_income_and_expense(
        year=year,
        month=month,
        tenant_code=tenant,
        db=db,
    )

    return _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )


@router.post(
    "/tax/monthly/finalize",
    response_model=MonthlyTaxSummaryRead,
    summary="Finalizacija mjesečnog obračuna i zapis u bazu",
    description=(
        "Finalizuje mjesečni porezni obračun za jednog tenanta i trajno ga upisuje "
        "u tabelu `tax_monthly_results`.\n\n"
        "Ako za isti `(tenant_code, year, month)` već postoji zapis, finalize "
        "se odbija sa HTTP 400.\n\n"
        "Primjer poziva:\n"
        "`POST /tax/monthly/finalize?year=2025&month=1` "
        "sa headerom `X-Tenant-Code: t-demo`."
    ),
    responses={
        200: {
            "description": (
                "Uspješno finalizovan mjesečni obračun. Vraća zaključani rezultat "
                "sa `is_final=true`."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "year": 2025,
                        "month": 1,
                        "tenant_code": "t-demo",
                        "total_income": "5000.00",
                        "total_expense": "1500.00",
                        "taxable_base": "2000.00",
                        "income_tax": "200.00",
                        "contributions_total": "520.00",
                        "total_due": "720.00",
                        "is_final": True,
                        "currency": "BAM",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "Poslovna greška pri finalizaciji.\n\n"
                "Tipični scenariji:\n"
                "- nedostaje `X-Tenant-Code` header → `Missing X-Tenant-Code header`\n"
                "- period je već finalizovan → "
                "`Monthly tax result for this period is already finalized`."
            ),
        },
        422: {
            "description": (
                "Validation error – npr. godina/mjesec van opsega ili pogrešan format "
                "query parametara."
            )
        },
    },
)
def finalize_monthly_tax(
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
            "Šifra tenanta za kojeg finalizujemo mjesečni obračun.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxSummaryRead:
    """
    Finalizuje mjesečni porezni obračun za jednog tenanta:

    1. Provjerava da li već postoji zapis u `tax_monthly_results`
       za zadati (tenant_code, year, month). Ako postoji → 400.
    2. Agregira prihode/rashode iz invoices + cash_entries (ista logika kao /auto).
    3. Primjenjuje DUMMY obračun (_compute_monthly_summary).
    4. Snima rezultat u `tax_monthly_results` kao finalizovan (`is_final=True`).
    5. Vraća izračunati rezultat sa `is_final=True`.

    Nakon što je mjesec finalizovan:
    - /tax/monthly/auto će vraćati persistirani rezultat (bez novog preračuna).
    - U narednim fazama ćemo dodati validaciju u invoices/cash module kako bi
      se spriječile izmjene podataka za već finalizovane periode.
    """
    tenant = _require_tenant(x_tenant_code)
    cfg = TAX_DUMMY_CONFIG

    # 1) Provjera da li već postoji finalizovan zapis
    existing = db.execute(
        select(TaxMonthlyResult).where(
            TaxMonthlyResult.tenant_code == tenant,
            TaxMonthlyResult.year == year,
            TaxMonthlyResult.month == month,
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail="Monthly tax result for this period is already finalized",
        )

    # 2) Agregacija prihoda/rashoda iz invoices + cash_entries
    total_income, total_expense = _aggregate_monthly_income_and_expense(
        year=year,
        month=month,
        tenant_code=tenant,
        db=db,
    )

    # 3) Izračun po DUMMY formuli
    summary = _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )

    # 4) Snimanje u bazu kao finalizovan rezultat
    db_obj = TaxMonthlyResult(
        tenant_code=tenant,
        year=summary.year,
        month=summary.month,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
        taxable_base=summary.taxable_base,
        income_tax=summary.income_tax,
        contributions_total=summary.contributions_total,
        total_due=summary.total_due,
        currency=summary.currency,
        is_final=True,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    # 5) Vraćamo summary, ali sa is_final=True
    return MonthlyTaxSummaryRead(
        year=summary.year,
        month=summary.month,
        tenant_code=summary.tenant_code,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
        taxable_base=summary.taxable_base,
        income_tax=summary.income_tax,
        contributions_total=summary.contributions_total,
        total_due=summary.total_due,
        is_final=True,
        currency=summary.currency,
    )


@router.get(
    "/tax/monthly/history",
    response_model=list[MonthlyTaxSummaryRead],
    summary="Pregled finalizovanih mjesečnih obračuna za godinu",
    description=(
        "Vraća listu svih finalizovanih mjesečnih poreznih obračuna za zadatu godinu "
        "i tenanta.\n\n"
        "Svaki element liste predstavlja jedan zapis iz `tax_monthly_results` "
        "mapiran u `MonthlyTaxSummaryRead` model.\n\n"
        "Ako za dati period nema finalizovanih obračuna, vraća se prazna lista."
    ),
    responses={
        200: {
            "description": (
                "Lista mjesečnih obračuna (može biti i prazna ako još nema podataka)."
            )
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
        },
        422: {
            "description": (
                "Validation error – npr. godina van opsega ili pogrešan format "
                "query parametara."
            )
        },
    },
)
def monthly_tax_history(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se traži istorija mjesečnih obračuna.",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg se čita istorija mjesečnih obračuna.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> list[MonthlyTaxSummaryRead]:
    """
    Čita sve finalizovane mjesečne porezne obračune iz `tax_monthly_results`
    za zadatu (year, tenant_code) kombinaciju.
    """
    tenant = _require_tenant(x_tenant_code)

    rows = (
        db.execute(
            select(TaxMonthlyResult)
            .where(
                TaxMonthlyResult.tenant_code == tenant,
                TaxMonthlyResult.year == year,
            )
            .order_by(TaxMonthlyResult.month.asc())
        )
        .scalars()
        .all()
    )

    return [
        MonthlyTaxSummaryRead(
            year=row.year,
            month=row.month,
            tenant_code=row.tenant_code,
            total_income=row.total_income,
            total_expense=row.total_expense,
            taxable_base=row.taxable_base,
            income_tax=row.income_tax,
            contributions_total=row.contributions_total,
            total_due=row.total_due,
            is_final=row.is_final,
            currency=row.currency,
        )
        for row in rows
    ]


@router.get(
    "/tax/monthly/status",
    response_model=MonthlyTaxStatusResponse,
    summary="Status mjesečnih obračuna po mjesecima za godinu",
    description=(
        "Vraća status mjesečnih obračuna za zadatu godinu i tenanta.\n\n"
        "Za svaki mjesec (1-12) označava da li postoji finalizovan obračun i da li "
        "postoji bilo kakav obračun (`has_data`).\n\n"
        "Ovo je idealno za kalendarski prikaz u UI-ju (npr. 'koji mjeseci su zaključani')."
    ),
    responses={
        200: {
            "description": (
                "Status za sve mjesece u zadatoj godini za konkretnog tenanta."
            )
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
        },
        422: {
            "description": (
                "Validation error – npr. godina van opsega ili pogrešan format "
                "query parametara."
            )
        },
    },
)
def monthly_tax_status(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se provjerava status mjesečnih obračuna.",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg se provjerava status mjesečnih obračuna.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxStatusResponse:
    """
    Vraća status mjesečnih obračuna za godinu/tenanta.

    Implementacija:
    - učita sve zapise iz `tax_monthly_results` za (tenant_code, year)
    - mapira ih po mjesecima
    - za mjesece koji nemaju zapis vraća `is_final=False`, `has_data=False`
    """
    tenant = _require_tenant(x_tenant_code)

    rows = (
        db.execute(
            select(TaxMonthlyResult).where(
                TaxMonthlyResult.tenant_code == tenant,
                TaxMonthlyResult.year == year,
            )
        )
        .scalars()
        .all()
    )

    by_month: dict[int, TaxMonthlyResult] = {row.month: row for row in rows}

    items = []
    for m in range(1, 13):
        row = by_month.get(m)
        if row is None:
            items.append(
                {
                    "month": m,
                    "is_final": False,
                    "has_data": False,
                }
            )
        else:
            items.append(
                {
                    "month": m,
                    "is_final": bool(row.is_final),
                    "has_data": True,
                }
            )

    return MonthlyTaxStatusResponse(
        year=year,
        tenant_code=tenant,
        items=items,
    )


@router.get(
    "/tax/yearly/preview",
    response_model=YearlyTaxSummaryRead,
    summary="Godišnji porezni obračun (preview) na osnovu finalizovanih mjeseci",
    description=(
        "Vraća **godišnji** porezni obračun za jednog tenanta na osnovu "
        "finalizovanih mjesečnih rezultata u tabeli `tax_monthly_results`.\n\n"
        "Logika:\n"
        "- pročita sve zapise za (tenant_code, year) sa `is_final = true`\n"
        "- sabere polja: `total_income`, `total_expense`, `taxable_base`, "
        "`income_tax`, `contributions_total`, `total_due`\n"
        "- vrati zbirne vrijednosti za cijelu godinu\n\n"
        "Ako nema finalizovanih mjeseci za zadatu godinu, vraća se 0 za sve iznose "
        "i `months_included = 0`."
    ),
    responses={
        200: {
            "description": "Uspješan preview godišnjeg poreznog obračuna.",
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
        },
        422: {
            "description": (
                "Validation error – npr. godina van opsega ili pogrešan format "
                "query parametara."
            )
        },
    },
)
def yearly_tax_preview(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
        description="Godina za koju se traži godišnji obračun.",
        examples=[2025],
    ),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg se računa godišnji obračun.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
    db: Session = Depends(_get_session_dep),
) -> YearlyTaxSummaryRead:
    """
    Godišnji porezni obračun na osnovu finalizovanih mjesečnih rezultata.

    Ne radi novi proračun po formuli, već **sabira** već izračunate
    mjesečne vrijednosti iz `tax_monthly_results` (DUMMY model).
    """
    tenant = _require_tenant(x_tenant_code)

    rows = (
        db.execute(
            select(TaxMonthlyResult).where(
                TaxMonthlyResult.tenant_code == tenant,
                TaxMonthlyResult.year == year,
                TaxMonthlyResult.is_final.is_(True),
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        # Nema finalizovanih mjeseci – vraćamo "prazan" godišnji obračun
        return YearlyTaxSummaryRead(
            year=year,
            tenant_code=tenant,
            months_included=0,
            total_income=Decimal("0.00"),
            total_expense=Decimal("0.00"),
            taxable_base=Decimal("0.00"),
            income_tax=Decimal("0.00"),
            contributions_total=Decimal("0.00"),
            total_due=Decimal("0.00"),
            currency="BAM",
        )

    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")
    taxable_base = Decimal("0.00")
    income_tax = Decimal("0.00")
    contributions_total = Decimal("0.00")
    total_due = Decimal("0.00")
    currency = rows[0].currency or "BAM"

    for row in rows:
        total_income += row.total_income
        total_expense += row.total_expense
        taxable_base += row.taxable_base
        income_tax += row.income_tax
        contributions_total += row.contributions_total
        total_due += row.total_due

    return YearlyTaxSummaryRead(
        year=year,
        tenant_code=tenant,
        months_included=len(rows),
        total_income=total_income,
        total_expense=total_expense,
        taxable_base=taxable_base,
        income_tax=income_tax,
        contributions_total=contributions_total,
        total_due=total_due,
        currency=currency,
    )
