# /home/miso/dev/sp-app/sp-app/backend/app/routes/tax.py
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import (
    CashEntry,
    Invoice,
    InputInvoice,
    TaxMonthlyResult,
    TaxYearlyResult,
    TaxMonthlyFinalizeHistory,
    TaxSettings,
    TaxMonthlyPayment,
    Tenant,
    TenantTaxProfileSettings,
    AppConstantsSet,
)
from app.schemas.tax import (
    ErrorResponse,
    MonthlyTaxStatusResponse,
    MonthlyTaxSummaryRead,
    TaxDummyConfig,
    YearlyTaxSummaryRead,
    TaxMonthlyOverviewResponse,
    TaxMonthlyOverviewItem,
    TaxMonthlyPaymentUpsert,
)
from app.schemas.tax_settings import TaxSettingsRead, TaxSettingsUpsert
from app.tenant_security import require_tenant_code

router = APIRouter(
    tags=["tax"],
)


# ======================================================
#  TENANT HELPERS
# ======================================================
def _require_tenant(x_tenant_code: Optional[str]) -> str:
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, tenant_code: str) -> None:
    """
    Osigurava da postoji red u tabeli `tenants` za dati tenant_code.

    Potrebno zbog FK relacija u nekim TAX tabelama (npr. tax_monthly_payments -> tenants.code).
    U testovima se često koristi novi tenant code bez eksplicitnog kreiranja tenanta,
    pa ovdje radimo "auto-create" samo kada je stvarno potrebno (write putanja).
    """
    exists = db.execute(select(Tenant).where(Tenant.code == tenant_code)).scalar_one_or_none()
    if exists is not None:
        return

    db.add(
        Tenant(
            id=uuid4().hex[:32],
            code=tenant_code,
            name=f"Auto-created tenant: {tenant_code}",
        )
    )
    db.commit()


# ======================================================
#  DEFAULT / FALLBACK KONFIGURACIJA (DUMMY)
# ======================================================
DEFAULT_TAX_CONFIG = TaxDummyConfig(
    income_tax_rate=Decimal("0.10"),
    pension_contribution_rate=Decimal("0.18"),
    health_contribution_rate=Decimal("0.12"),
    unemployment_contribution_rate=Decimal("0.015"),
    flat_costs_rate=Decimal("0.30"),
    currency="BAM",
)

# BACKWARD COMPATIBILITY:
# Postojeći testovi importuju TAX_DUMMY_CONFIG iz app.routes.tax
TAX_DUMMY_CONFIG = DEFAULT_TAX_CONFIG


# ======================================================
#  APP CONSTANTS (effective-dated) helpers
# ======================================================
def _normalize_jurisdiction(entity_value: str) -> str:
    """
    Normalizacija vrijednosti iz settings/tax (entity) na jurisdikciju u app_constants_sets.

    Očekujemo:
      - RS
      - FBiH
      - BD  (Brčko distrikt)
    """
    v = (entity_value or "").strip()
    if not v:
        return "RS"

    upper = v.upper()

    if upper in {"RS"}:
        return "RS"
    if upper in {"FBIH", "FEDERACIJA", "FEDERACIJA BIH"}:
        return "FBiH"
    if upper in {"BD", "BRCKO", "BRČKO", "BRCKO DISTRIKT", "BRČKO DISTRIKT"}:
        return "BD"

    # Ako dođe nešto neočekivano, držimo se defaulta
    return "RS"


def _default_scenario_key_for_profile(prof: TenantTaxProfileSettings) -> Optional[str]:
    """
    Fallback mapiranje za profile koji još nemaju eksplicitno postavljen scenario_key.

    Važno za backward compatibility:
    - stari testovi i stari podaci mogu imati entity + has_additional_activity,
      bez scenario_key.
    """
    entity = (prof.entity or "").strip()

    if entity == "RS":
        return "rs_supplementary" if bool(prof.has_additional_activity) else "rs_primary"
    if entity == "FBiH":
        return "fbih_obrt"
    if entity in {"Brcko", "BD"}:
        return "bd_samostalna"

    return None


def _find_current_constants_set(
    *,
    db: Session,
    jurisdiction: str,
    as_of: date,
    scenario_key: Optional[str] = None,
) -> Optional[AppConstantsSet]:
    """
    Vraća set koji je aktivan na datum `as_of`:
      effective_from <= as_of AND (effective_to IS NULL OR effective_to >= as_of)

    Ako je scenario_key zadat, lookup je strožiji:
      jurisdiction + scenario_key + date

    Ako ih ima više (ne bi smjelo), uzima najnoviji po effective_from.
    """
    stmt = (
        select(AppConstantsSet)
        .where(
            AppConstantsSet.jurisdiction == jurisdiction,
            AppConstantsSet.effective_from <= as_of,
            or_(AppConstantsSet.effective_to.is_(None), AppConstantsSet.effective_to >= as_of),
        )
        .order_by(AppConstantsSet.effective_from.desc(), AppConstantsSet.id.desc())
        .limit(1)
    )

    if scenario_key:
        stmt = stmt.where(AppConstantsSet.scenario_key == scenario_key)

    return db.execute(stmt).scalar_one_or_none()


def _decimal_from_payload(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def _tax_config_from_constants_payload(payload: dict[str, Any]) -> Optional[TaxDummyConfig]:
    """
    Izvlači TAX stope iz JSON payload-a u app_constants_sets.

    Podržani oblici:

    A) Legacy root keys:
       {
         "income_tax_rate": 0.10,
         "pension_contribution_rate": 0.18,
         ...
         "currency": "BAM"
       }

    B) Legacy nested under "tax":
       {
         "tax": {
           "income_tax_rate": 0.10,
           "pension_contribution_rate": 0.18,
           ...
           "currency": "BAM"
         }
       }

    C) V2 payload shape:
       {
         "base": {
           "currency": "BAM"
         },
         "tax": {
           "income_tax_rate": 0.10,
           "flat_costs_rate": 0.30
         },
         "contributions": {
           "pension_rate": 0.18,
           "health_rate": 0.12,
           "unemployment_rate": 0.015
         }
       }

    Ako payload nema ništa relevantno → vrati None.
    """
    if not isinstance(payload, dict):
        return None

    tax_block = payload.get("tax") if isinstance(payload.get("tax"), dict) else {}
    contrib_block = payload.get("contributions") if isinstance(payload.get("contributions"), dict) else {}
    base_block = payload.get("base") if isinstance(payload.get("base"), dict) else {}

    has_any_relevant = any(
        key in payload
        for key in {
            "income_tax_rate",
            "pension_contribution_rate",
            "health_contribution_rate",
            "unemployment_contribution_rate",
            "flat_costs_rate",
            "currency",
        }
    ) or any(
        key in tax_block
        for key in {
            "income_tax_rate",
            "pension_contribution_rate",
            "health_contribution_rate",
            "unemployment_contribution_rate",
            "flat_costs_rate",
            "currency",
        }
    ) or any(
        key in contrib_block
        for key in {
            "pension_rate",
            "health_rate",
            "unemployment_rate",
        }
    ) or ("currency" in base_block)

    if not has_any_relevant:
        return None

    inc = _decimal_from_payload(
        tax_block.get("income_tax_rate", payload.get("income_tax_rate"))
    )

    # Legacy ili V2 contributions mapping
    pen = _decimal_from_payload(
        contrib_block.get(
            "pension_rate",
            tax_block.get("pension_contribution_rate", payload.get("pension_contribution_rate")),
        )
    )
    hea = _decimal_from_payload(
        contrib_block.get(
            "health_rate",
            tax_block.get("health_contribution_rate", payload.get("health_contribution_rate")),
        )
    )
    une = _decimal_from_payload(
        contrib_block.get(
            "unemployment_rate",
            tax_block.get("unemployment_contribution_rate", payload.get("unemployment_contribution_rate")),
        )
    )

    flat = _decimal_from_payload(
        tax_block.get("flat_costs_rate", payload.get("flat_costs_rate"))
    )

    cur = (
        base_block.get("currency")
        or tax_block.get("currency")
        or payload.get("currency")
    )

    return TaxDummyConfig(
        income_tax_rate=inc if inc is not None else DEFAULT_TAX_CONFIG.income_tax_rate,
        pension_contribution_rate=pen if pen is not None else DEFAULT_TAX_CONFIG.pension_contribution_rate,
        health_contribution_rate=hea if hea is not None else DEFAULT_TAX_CONFIG.health_contribution_rate,
        unemployment_contribution_rate=une if une is not None else DEFAULT_TAX_CONFIG.unemployment_contribution_rate,
        flat_costs_rate=flat if flat is not None else DEFAULT_TAX_CONFIG.flat_costs_rate,
        currency=str(cur) if cur is not None else DEFAULT_TAX_CONFIG.currency,
    )


def _resolve_tax_config(db: Session, tenant_code: str, as_of: date) -> TaxDummyConfig:
    """
    Hijerarhija izvora konfiguracije (prioritet):
      1) tax_settings (tenant override)
      2) app_constants_sets (effective-dated po jurisdikciji + scenario_key)
         **samo ako tenant ima /settings/tax profil**
      3) DEFAULT_TAX_CONFIG (fallback)
    """
    # 1) tenant override
    row = db.execute(select(TaxSettings).where(TaxSettings.tenant_code == tenant_code)).scalar_one_or_none()
    if row is not None:
        return TaxDummyConfig(
            income_tax_rate=Decimal(str(row.income_tax_rate)),
            pension_contribution_rate=Decimal(str(row.pension_contribution_rate)),
            health_contribution_rate=Decimal(str(row.health_contribution_rate)),
            unemployment_contribution_rate=Decimal(str(row.unemployment_contribution_rate)),
            flat_costs_rate=Decimal(str(row.flat_costs_rate)),
            currency=row.currency or DEFAULT_TAX_CONFIG.currency,
        )

    # 2) constants set koristimo samo ako tenant eksplicitno ima tax profil (settings/tax)
    prof = db.execute(
        select(TenantTaxProfileSettings).where(TenantTaxProfileSettings.tenant_code == tenant_code)
    ).scalar_one_or_none()

    if prof is not None and (prof.entity or "").strip():
        jurisdiction = _normalize_jurisdiction(prof.entity)
        scenario_key = (prof.scenario_key or "").strip() or _default_scenario_key_for_profile(prof)

        cs = _find_current_constants_set(
            db=db,
            jurisdiction=jurisdiction,
            scenario_key=scenario_key,
            as_of=as_of,
        )
        if cs is not None:
            cfg = _tax_config_from_constants_payload(cs.payload or {})
            if cfg is not None:
                return cfg

        # Backward fallback:
        # ako za taj scenario nema seta, pokušaj po jurisdikciji (stari podaci)
        cs_fallback = _find_current_constants_set(
            db=db,
            jurisdiction=jurisdiction,
            as_of=as_of,
            scenario_key=None,
        )
        if cs_fallback is not None:
            cfg = _tax_config_from_constants_payload(cs_fallback.payload or {})
            if cfg is not None:
                return cfg

    # 3) fallback
    return DEFAULT_TAX_CONFIG


# ======================================================
#  TAX SETTINGS (GET/PUT)
# ======================================================
@router.get(
    "/tax/settings",
    response_model=TaxSettingsRead,
    summary="Učitavanje TAX stopa (settings) za tenant",
    description=(
        "Vraća trenutno podešene TAX stope za tenant. "
        "Ako tenant nema podešavanja u bazi, vraća default vrijednosti "
        "(i ne kreira red u bazi)."
    ),
    operation_id="tax_settings_get",
)
def get_tax_settings(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> TaxSettingsRead:
    tenant = _require_tenant(x_tenant_code)

    row = db.execute(select(TaxSettings).where(TaxSettings.tenant_code == tenant)).scalar_one_or_none()
    if row is None:
        cfg = DEFAULT_TAX_CONFIG
        return TaxSettingsRead(
            tenant_code=tenant,
            income_tax_rate=cfg.income_tax_rate,
            pension_contribution_rate=cfg.pension_contribution_rate,
            health_contribution_rate=cfg.health_contribution_rate,
            unemployment_contribution_rate=cfg.unemployment_contribution_rate,
            flat_costs_rate=cfg.flat_costs_rate,
            currency=cfg.currency,
        )

    return TaxSettingsRead.model_validate(row)


@router.put(
    "/tax/settings",
    response_model=TaxSettingsRead,
    summary="Upsert TAX stopa (settings) za tenant",
    description=(
        "Upsert (insert/update) TAX stopa za tenant. "
        "Sva polja su opciona; ako je nešto izostavljeno, zadržava se postojeća "
        "vrijednost (ili default ako se red tek kreira)."
    ),
    operation_id="tax_settings_put",
)
def upsert_tax_settings(
    payload: TaxSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> TaxSettingsRead:
    tenant = _require_tenant(x_tenant_code)

    # FK safety: tax_settings.tenant_code -> tenants.code
    _ensure_tenant_exists(db, tenant)

    row = db.execute(select(TaxSettings).where(TaxSettings.tenant_code == tenant)).scalar_one_or_none()

    if row is None:
        cfg = DEFAULT_TAX_CONFIG
        row = TaxSettings(
            tenant_code=tenant,
            income_tax_rate=cfg.income_tax_rate,
            pension_contribution_rate=cfg.pension_contribution_rate,
            health_contribution_rate=cfg.health_contribution_rate,
            unemployment_contribution_rate=cfg.unemployment_contribution_rate,
            flat_costs_rate=cfg.flat_costs_rate,
            currency=cfg.currency,
        )
        db.add(row)

    if payload.income_tax_rate is not None:
        row.income_tax_rate = payload.income_tax_rate
    if payload.pension_contribution_rate is not None:
        row.pension_contribution_rate = payload.pension_contribution_rate
    if payload.health_contribution_rate is not None:
        row.health_contribution_rate = payload.health_contribution_rate
    if payload.unemployment_contribution_rate is not None:
        row.unemployment_contribution_rate = payload.unemployment_contribution_rate
    if payload.flat_costs_rate is not None:
        row.flat_costs_rate = payload.flat_costs_rate
    if payload.currency is not None:
        row.currency = payload.currency

    db.commit()
    db.refresh(row)

    return TaxSettingsRead.model_validate(row)


# ======================================================
#  INTERNE POMOĆNE FUNKCIJE
# ======================================================
def _month_bounds(year: int, month: int) -> tuple[date, date]:
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
    flat_costs = total_income * cfg.flat_costs_rate

    taxable_base = total_income - flat_costs - total_expense
    if taxable_base < Decimal("0"):
        taxable_base = Decimal("0.00")

    income_tax = taxable_base * cfg.income_tax_rate

    contributions_rate_sum = (
        cfg.pension_contribution_rate + cfg.health_contribution_rate + cfg.unemployment_contribution_rate
    )
    contributions_total = taxable_base * contributions_rate_sum

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
    month_start, month_end = _month_bounds(year, month)

    stmt_invoices = select(func.coalesce(func.sum(Invoice.total_amount), 0).label("invoice_income")).where(
        Invoice.tenant_code == tenant_code,
        Invoice.issue_date >= month_start,
        Invoice.issue_date < month_end,
    )
    invoice_row = db.execute(stmt_invoices).one()
    invoice_income = invoice_row.invoice_income or Decimal("0.00")

    income_expr = func.coalesce(
        func.sum(case((CashEntry.kind == "income", CashEntry.amount), else_=0)),
        0,
    )

    expense_expr = func.coalesce(
        func.sum(case((CashEntry.kind == "expense", CashEntry.amount), else_=0)),
        0,
    )

    stmt_cash = select(income_expr.label("cash_income"), expense_expr.label("cash_expense")).where(
        CashEntry.tenant_code == tenant_code,
        CashEntry.entry_date >= month_start,
        CashEntry.entry_date < month_end,
    )

    cash_row = db.execute(stmt_cash).one()
    cash_income = cash_row.cash_income or Decimal("0.00")
    cash_expense = cash_row.cash_expense or Decimal("0.00")

    stmt_input_invoices = select(func.coalesce(func.sum(InputInvoice.total_amount), 0).label("input_expense")).where(
        InputInvoice.tenant_code == tenant_code,
        InputInvoice.issue_date >= month_start,
        InputInvoice.issue_date < month_end,
    )
    input_row = db.execute(stmt_input_invoices).one()
    input_expense = input_row.input_expense or Decimal("0.00")

    total_income = invoice_income + cash_income
    total_expense = cash_expense + input_expense

    return total_income, total_expense


def _compute_monthly_components_from_base(
    *,
    taxable_base: Decimal,
    cfg: TaxDummyConfig,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if taxable_base < Decimal("0"):
        taxable_base = Decimal("0.00")

    income_tax = taxable_base * cfg.income_tax_rate
    pension = taxable_base * cfg.pension_contribution_rate
    health = taxable_base * cfg.health_contribution_rate
    unemployment = taxable_base * cfg.unemployment_contribution_rate

    return income_tax, pension, health, unemployment


def _get_monthly_summary_any(
    *,
    year: int,
    month: int,
    tenant_code: str,
    db: Session,
) -> MonthlyTaxSummaryRead:
    """
    Vraća summary za mjesec:
      - ako postoji finalizovan zapis u tax_monthly_results → vrati ga
      - inače izračunaj iz invoices + cash + input_invoices koristeći cfg za taj mjesec (as_of = 1. dan mjeseca)
    """
    existing = db.execute(
        select(TaxMonthlyResult).where(
            TaxMonthlyResult.tenant_code == tenant_code,
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

    as_of = date(year, month, 1)
    cfg = _resolve_tax_config(db, tenant_code, as_of=as_of)

    total_income, total_expense = _aggregate_monthly_income_and_expense(
        year=year,
        month=month,
        tenant_code=tenant_code,
        db=db,
    )

    return _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant_code,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )


# ======================================================
#  10.1 /tax/monthly – mjesečni pregled (12 mjeseci)
# ======================================================
@router.get(
    "/tax/monthly",
    response_model=TaxMonthlyOverviewResponse,
    summary="Mjesečni pregled obaveza (1-12) + status uplate",
    operation_id="tax_monthly_overview",
    responses={400: {"model": ErrorResponse}},
)
def tax_monthly_overview(
    year: int = Query(..., ge=2000, le=2100),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> TaxMonthlyOverviewResponse:
    tenant = _require_tenant(x_tenant_code)

    payments = (
        db.execute(
            select(TaxMonthlyPayment).where(
                TaxMonthlyPayment.tenant_code == tenant,
                TaxMonthlyPayment.year == year,
            )
        )
        .scalars()
        .all()
    )
    payment_by_month = {p.month: p for p in payments}

    items: list[TaxMonthlyOverviewItem] = []
    for m in range(1, 13):
        summary = _get_monthly_summary_any(year=year, month=m, tenant_code=tenant, db=db)

        cfg = _resolve_tax_config(db, tenant, as_of=date(year, m, 1))
        income_tax, pension, health, unemployment = _compute_monthly_components_from_base(
            taxable_base=Decimal(str(summary.taxable_base)),
            cfg=cfg,
        )
        total_due = income_tax + pension + health + unemployment

        pay = payment_by_month.get(m)
        items.append(
            TaxMonthlyOverviewItem(
                year=year,
                month=m,
                income_tax=income_tax,
                pension=pension,
                health=health,
                unemployment=unemployment,
                total_due=total_due,
                is_paid=bool(pay.is_paid) if pay is not None else False,
                paid_at=pay.paid_at if pay is not None else None,
                currency=cfg.currency,
            )
        )

    return TaxMonthlyOverviewResponse(
        year=year,
        tenant_code=tenant,
        items=items,
    )


@router.put(
    "/tax/monthly/{year}/{month}/payment",
    response_model=TaxMonthlyOverviewItem,
    summary="Označi uplatu za mjesec (DA/NE) + datum uplate",
    operation_id="tax_monthly_payment_upsert",
    responses={400: {"model": ErrorResponse}},
)
def upsert_monthly_payment(
    year: int,
    month: int,
    payload: TaxMonthlyPaymentUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> TaxMonthlyOverviewItem:
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year")
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")

    tenant = _require_tenant(x_tenant_code)

    # FK safety: tax_monthly_payments.tenant_code -> tenants.code
    _ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TaxMonthlyPayment).where(
            TaxMonthlyPayment.tenant_code == tenant,
            TaxMonthlyPayment.year == year,
            TaxMonthlyPayment.month == month,
        )
    ).scalar_one_or_none()

    if row is None:
        row = TaxMonthlyPayment(
            tenant_code=tenant,
            year=year,
            month=month,
            is_paid=False,
            paid_at=None,
        )
        db.add(row)

    row.is_paid = bool(payload.is_paid)
    if row.is_paid:
        row.paid_at = payload.paid_at or date.today()
    else:
        row.paid_at = None

    db.commit()
    db.refresh(row)

    as_of = date(year, month, 1)
    cfg = _resolve_tax_config(db, tenant, as_of=as_of)

    summary = _get_monthly_summary_any(year=year, month=month, tenant_code=tenant, db=db)

    income_tax, pension, health, unemployment = _compute_monthly_components_from_base(
        taxable_base=Decimal(str(summary.taxable_base)),
        cfg=cfg,
    )
    total_due = income_tax + pension + health + unemployment

    return TaxMonthlyOverviewItem(
        year=year,
        month=month,
        income_tax=income_tax,
        pension=pension,
        health=health,
        unemployment=unemployment,
        total_due=total_due,
        is_paid=row.is_paid,
        paid_at=row.paid_at,
        currency=cfg.currency,
    )


# ======================================================
#  MJESEČNI OBRAČUN – PREVIEW
# ======================================================
@router.get(
    "/tax/monthly/preview",
    response_model=MonthlyTaxSummaryRead,
    summary="Mjesečni porezni obračun (preview, ručni unos)",
    operation_id="tax_monthly_preview",
    responses={400: {"model": ErrorResponse}},
)
def preview_monthly_tax(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    total_income: Decimal = Query(..., ge=0),
    total_expense: Decimal = Query(0, ge=0),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxSummaryRead:
    tenant = _require_tenant(x_tenant_code)
    cfg = _resolve_tax_config(db, tenant, as_of=date(year, month, 1))

    return _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )


# ======================================================
#  MJESEČNI OBRAČUN – AUTO
# ======================================================
@router.get(
    "/tax/monthly/auto",
    response_model=MonthlyTaxSummaryRead,
    summary="Automatski mjesečni obračun iz invoices + cash + input_invoices",
    operation_id="tax_monthly_auto",
    responses={400: {"model": ErrorResponse}},
)
def auto_monthly_tax(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxSummaryRead:
    tenant = _require_tenant(x_tenant_code)
    return _get_monthly_summary_any(year=year, month=month, tenant_code=tenant, db=db)


# ======================================================
#  MJESEČNI OBRAČUN – FINALIZE
# ======================================================
@router.post(
    "/tax/monthly/finalize",
    response_model=MonthlyTaxSummaryRead,
    summary="Finalizacija mjesečnog obračuna i zapis u bazu",
    operation_id="tax_monthly_finalize",
    responses={400: {"model": ErrorResponse}},
)
def finalize_monthly_tax(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxSummaryRead:
    tenant = _require_tenant(x_tenant_code)
    cfg = _resolve_tax_config(db, tenant, as_of=date(year, month, 1))

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

    total_income, total_expense = _aggregate_monthly_income_and_expense(
        year=year,
        month=month,
        tenant_code=tenant,
        db=db,
    )

    summary = _compute_monthly_summary(
        year=year,
        month=month,
        tenant_code=tenant,
        total_income=total_income,
        total_expense=total_expense,
        cfg=cfg,
    )

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

    history_obj = TaxMonthlyFinalizeHistory(
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
        action="finalize",
        triggered_by=None,
        note=None,
    )

    db.add_all([db_obj, history_obj])
    db.commit()
    db.refresh(db_obj)

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


# ======================================================
#  MJESEČNA ISTORIJA & STATUS
# ======================================================
@router.get(
    "/tax/monthly/history",
    response_model=list[MonthlyTaxSummaryRead],
    summary="Istorija finalizovanih mjesečnih obračuna za godinu",
    operation_id="tax_monthly_history",
    responses={400: {"model": ErrorResponse}},
)
def monthly_tax_history(
    year: int = Query(..., ge=2000, le=2100),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> list[MonthlyTaxSummaryRead]:
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
    operation_id="tax_monthly_status",
    responses={400: {"model": ErrorResponse}},
)
def monthly_tax_status(
    year: int = Query(..., ge=2000, le=2100),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> MonthlyTaxStatusResponse:
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
            items.append({"month": m, "is_final": False, "has_data": False})
        else:
            items.append({"month": m, "is_final": bool(row.is_final), "has_data": True})

    return MonthlyTaxStatusResponse(
        year=year,
        tenant_code=tenant,
        items=items,
    )


# ======================================================
#  MJESEČNI OBRAČUN – CSV EXPORT
# ======================================================
@router.get(
    "/tax/monthly/export",
    summary="Export mjesečnog poreznog obračuna u CSV",
)
def export_monthly_tax_csv(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> Response:
    summary = auto_monthly_tax(
        year=year,
        month=month,
        x_tenant_code=x_tenant_code,
        db=db,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(
        [
            "year",
            "month",
            "tenant_code",
            "total_income",
            "total_expense",
            "taxable_base",
            "income_tax",
            "contributions_total",
            "total_due",
            "currency",
            "is_final",
        ]
    )

    writer.writerow(
        [
            summary.year,
            summary.month,
            summary.tenant_code,
            str(summary.total_income),
            str(summary.total_expense),
            str(summary.taxable_base),
            str(summary.income_tax),
            str(summary.contributions_total),
            str(summary.total_due),
            summary.currency,
            "true" if summary.is_final else "false",
        ]
    )

    csv_content = buffer.getvalue()
    buffer.close()

    filename = f"tax-monthly-{summary.tenant_code}-{summary.year}-{summary.month:02d}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ======================================================
#  GODIŠNJI OBRAČUN – PREVIEW
# ======================================================
@router.get(
    "/tax/yearly/preview",
    response_model=YearlyTaxSummaryRead,
    summary="Godišnji porezni obračun (preview) na osnovu finalizovanih mjeseci",
    operation_id="tax_yearly_preview",
    responses={400: {"model": ErrorResponse}},
)
def yearly_tax_preview(
    year: int = Query(..., ge=2000, le=2100),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> YearlyTaxSummaryRead:
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


# ======================================================
#  GODIŠNJI OBRAČUN – FINALIZE
# ======================================================
@router.post(
    "/tax/yearly/finalize",
    response_model=YearlyTaxSummaryRead,
    summary="Finalizacija godišnjeg poreznog obračuna i zapis u bazu",
    operation_id="tax_yearly_finalize",
    responses={400: {"model": ErrorResponse}},
)
def yearly_tax_finalize(
    year: int = Query(..., ge=2000, le=2100),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> YearlyTaxSummaryRead:
    tenant = _require_tenant(x_tenant_code)

    existing = db.execute(
        select(TaxYearlyResult).where(
            TaxYearlyResult.tenant_code == tenant,
            TaxYearlyResult.year == year,
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail="Yearly tax result for this year is already finalized",
        )

    monthly_rows = (
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

    if not monthly_rows:
        raise HTTPException(
            status_code=400,
            detail=(
                "No finalized monthly tax results for this year; "
                "cannot finalize yearly tax result"
            ),
        )

    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")
    taxable_base = Decimal("0.00")
    income_tax = Decimal("0.00")
    contributions_total = Decimal("0.00")
    total_due = Decimal("0.00")
    currency = monthly_rows[0].currency or "BAM"

    for row in monthly_rows:
        total_income += row.total_income
        total_expense += row.total_expense
        taxable_base += row.taxable_base
        income_tax += row.income_tax
        contributions_total += row.contributions_total
        total_due += row.total_due

    months_included = len(monthly_rows)

    db_obj = TaxYearlyResult(
        tenant_code=tenant,
        year=year,
        months_included=months_included,
        total_income=total_income,
        total_expense=total_expense,
        taxable_base=taxable_base,
        income_tax=income_tax,
        contributions_total=contributions_total,
        total_due=total_due,
        currency=currency,
        is_final=True,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    return YearlyTaxSummaryRead(
        year=year,
        tenant_code=tenant,
        months_included=months_included,
        total_income=total_income,
        total_expense=total_expense,
        taxable_base=taxable_base,
        income_tax=income_tax,
        contributions_total=contributions_total,
        total_due=total_due,
        currency=currency,
    )


# ======================================================
#  GODIŠNJI OBRAČUN – CSV EXPORT
# ======================================================
@router.get(
    "/tax/yearly/export",
    summary="Export godišnjeg poreznog obračuna u CSV",
)
def export_yearly_tax_csv(
    year: int = Query(..., ge=2000, le=2100),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> Response:
    summary = yearly_tax_preview(year=year, x_tenant_code=x_tenant_code, db=db)

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(
        [
            "year",
            "tenant_code",
            "months_included",
            "total_income",
            "total_expense",
            "taxable_base",
            "income_tax",
            "contributions_total",
            "total_due",
            "currency",
        ]
    )

    writer.writerow(
        [
            summary.year,
            summary.tenant_code,
            summary.months_included,
            str(summary.total_income),
            str(summary.total_expense),
            str(summary.taxable_base),
            str(summary.income_tax),
            str(summary.contributions_total),
            str(summary.total_due),
            summary.currency,
        ]
    )

    csv_content = buffer.getvalue()
    buffer.close()

    filename = f"tax-yearly-{summary.tenant_code}-{summary.year}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )