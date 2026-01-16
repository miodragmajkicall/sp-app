# /home/miso/dev/sp-app/sp-app/backend/app/routes/admin_constants.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AppConstantsSet
from app.schemas.constants import (
    ALLOWED_SCENARIOS,
    AppConstantsSetCreate,
    AppConstantsSetListResponse,
    AppConstantsSetRead,
    AppConstantsSetUpdate,
)

router = APIRouter(tags=["admin"])


def _get_db() -> Session:
    return SessionLocal()


def _validate_scenario(jurisdiction: str, scenario_key: str) -> None:
    allowed = ALLOWED_SCENARIOS.get(jurisdiction)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported jurisdiction: {jurisdiction}")
    if scenario_key not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid scenario_key '{scenario_key}' for jurisdiction '{jurisdiction}'. "
                f"Allowed: {sorted(list(allowed))}"
            ),
        )


def _ranges_overlap(
    *,
    a_from: date,
    a_to: Optional[date],
    b_from: date,
    b_to: Optional[date],
) -> bool:
    # Zatvoreni intervali [from, to], None = ∞
    if a_to is not None and b_from > a_to:
        return False
    if b_to is not None and a_from > b_to:
        return False
    return True


def _ensure_no_overlap(
    *,
    db: Session,
    jurisdiction: str,
    scenario_key: str,
    effective_from: date,
    effective_to: Optional[date],
    exclude_id: Optional[int] = None,
) -> None:
    stmt = select(AppConstantsSet).where(
        AppConstantsSet.jurisdiction == jurisdiction,
        AppConstantsSet.scenario_key == scenario_key,
    )
    if exclude_id is not None:
        stmt = stmt.where(AppConstantsSet.id != exclude_id)

    rows = db.execute(stmt).scalars().all()
    for row in rows:
        if _ranges_overlap(
            a_from=row.effective_from,
            a_to=row.effective_to,
            b_from=effective_from,
            b_to=effective_to,
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Overlapping effective date range for this jurisdiction+scenario. "
                    f"Conflicts with id={row.id} [{row.effective_from}..{row.effective_to}]"
                ),
            )


def _find_current_set(
    *,
    db: Session,
    jurisdiction: str,
    scenario_key: str,
    as_of: date,
) -> Optional[AppConstantsSet]:
    stmt = (
        select(AppConstantsSet)
        .where(
            AppConstantsSet.jurisdiction == jurisdiction,
            AppConstantsSet.scenario_key == scenario_key,
            AppConstantsSet.effective_from <= as_of,
            or_(AppConstantsSet.effective_to.is_(None), AppConstantsSet.effective_to >= as_of),
        )
        .order_by(AppConstantsSet.effective_from.desc(), AppConstantsSet.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _rollover_close_previous_if_needed(
    *,
    db: Session,
    jurisdiction: str,
    scenario_key: str,
    new_from: date,
    actor: Optional[str],
    reason: str,
) -> None:
    """
    Rollover samo za open-ended prethodni set (effective_to IS NULL), u okviru (jurisdiction+scenario_key):
    - Ako postoji aktivan open-ended set na new_from, zatvori ga na (new_from - 1 dan).
    - Ako je prethodni set već imao effective_to (zatvoren period), NE diramo ga (overlap ide na 400).
    """
    prev = _find_current_set(db=db, jurisdiction=jurisdiction, scenario_key=scenario_key, as_of=new_from)
    if prev is None:
        return

    if prev.effective_to is not None:
        return

    if new_from <= prev.effective_from:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot rollover: new effective_from must be AFTER current set's effective_from. "
                f"Current id={prev.id} starts at {prev.effective_from}, new starts at {new_from}."
            ),
        )

    prev.effective_to = new_from - timedelta(days=1)
    prev.updated_by = actor
    prev.updated_reason = reason or "rollover"
    prev.updated_at = datetime.utcnow()


# ----------------------------
# Minimal semantic validation
# (NO payload mutation, NO computed checks)
# ----------------------------


def _as_number(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _get_path(payload: dict[str, Any], path: list[str]) -> Any:
    cur: Any = payload
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _validate_rate_0_1(*, name: str, v: Any) -> None:
    n = _as_number(v)
    if n is None:
        return
    if n < 0 or n > 1:
        raise HTTPException(status_code=400, detail=f"{name} must be between 0 and 1 (decimal). Got {n}.")


def _validate_percent_0_100(*, name: str, v: Any) -> None:
    n = _as_number(v)
    if n is None:
        return
    if n < 0 or n > 100:
        raise HTTPException(status_code=400, detail=f"{name} must be between 0 and 100 (percent). Got {n}.")


def _validate_positive(*, name: str, v: Any) -> None:
    n = _as_number(v)
    if n is None:
        return
    if n <= 0:
        raise HTTPException(status_code=400, detail=f"{name} must be > 0. Got {n}.")


def _validate_payload_semantics(*, jurisdiction: str, payload: Any) -> None:
    """
    Minimalne validacije koje nisu "computed":
    - stope 0..1 (decimal)
    - procenti 0..100
    - osnovice > 0
    Ostavlja slobodu FE da definiše tačan shape; backend samo sanity-check ako su ključevi prisutni.
    """
    if not isinstance(payload, dict):
        return

    # Common (if present)
    _validate_rate_0_1(name="vat.standard_rate", v=_get_path(payload, ["vat", "standard_rate"]))
    _validate_rate_0_1(name="tax.income_tax_rate", v=_get_path(payload, ["tax", "income_tax_rate"]))

    # Contributions (new-ish UI shape if present)
    _validate_rate_0_1(name="contributions.pension_rate", v=_get_path(payload, ["contributions", "pension_rate"]))
    _validate_rate_0_1(name="contributions.health_rate", v=_get_path(payload, ["contributions", "health_rate"]))
    _validate_rate_0_1(name="contributions.unemployment_rate", v=_get_path(payload, ["contributions", "unemployment_rate"]))

    # Legacy tax payload (still supported if present)
    _validate_rate_0_1(name="tax.pension_contribution_rate", v=_get_path(payload, ["tax", "pension_contribution_rate"]))
    _validate_rate_0_1(name="tax.health_contribution_rate", v=_get_path(payload, ["tax", "health_contribution_rate"]))
    _validate_rate_0_1(
        name="tax.unemployment_contribution_rate", v=_get_path(payload, ["tax", "unemployment_contribution_rate"])
    )
    _validate_rate_0_1(name="tax.flat_costs_rate", v=_get_path(payload, ["tax", "flat_costs_rate"]))

    base = payload.get("base") if isinstance(payload.get("base"), dict) else {}

    if jurisdiction == "FBiH":
        _validate_positive(name="base.monthly_contrib_base_bam", v=base.get("monthly_contrib_base_bam"))

    if jurisdiction == "RS":
        _validate_positive(name="base.avg_gross_wage_prev_year_bam", v=base.get("avg_gross_wage_prev_year_bam"))
        _validate_percent_0_100(name="base.contrib_base_percent_of_avg_gross", v=base.get("contrib_base_percent_of_avg_gross"))

    if jurisdiction == "BD":
        _validate_positive(name="base.avg_gross_prev_year_bam", v=base.get("avg_gross_prev_year_bam"))
        _validate_percent_0_100(name="base.base_percent_of_avg_gross", v=base.get("base_percent_of_avg_gross"))


@router.get(
    "/admin/constants",
    response_model=AppConstantsSetListResponse,
    summary="Admin: list setova zakonskih konstanti (effective-dated) po jurisdikciji i scenariju",
    operation_id="admin_constants_list",
)
def admin_constants_list(
    jurisdiction: Optional[str] = Query(None, description="RS / FBiH / BD"),
    scenario_key: Optional[str] = Query(None, description="scenario_key (npr. rs_primary)"),
) -> AppConstantsSetListResponse:
    db = _get_db()
    try:
        stmt = select(AppConstantsSet).order_by(
            AppConstantsSet.jurisdiction.asc(),
            AppConstantsSet.scenario_key.asc(),
            AppConstantsSet.effective_from.desc(),
            AppConstantsSet.id.desc(),
        )
        if jurisdiction:
            stmt = stmt.where(AppConstantsSet.jurisdiction == jurisdiction)
        if scenario_key:
            stmt = stmt.where(AppConstantsSet.scenario_key == scenario_key)

        rows = db.execute(stmt).scalars().all()
        items = [AppConstantsSetRead.model_validate(r) for r in rows]
        return AppConstantsSetListResponse(items=items)
    finally:
        db.close()


@router.post(
    "/admin/constants",
    response_model=AppConstantsSetRead,
    summary="Admin: kreiraj novi set konstanti (rollover zatvara samo open-ended prethodni set u okviru scenario_key)",
    operation_id="admin_constants_create",
    responses={400: {"description": "Validation / overlap error"}},
)
def admin_constants_create(payload: AppConstantsSetCreate) -> AppConstantsSetRead:
    db = _get_db()
    try:
        _validate_scenario(payload.jurisdiction, payload.scenario_key)

        # Minimal semantic validation BEFORE any rollover mutation
        _validate_payload_semantics(jurisdiction=payload.jurisdiction, payload=payload.payload)

        # 1) Rollover only within same (jurisdiction+scenario)
        _rollover_close_previous_if_needed(
            db=db,
            jurisdiction=payload.jurisdiction,
            scenario_key=payload.scenario_key,
            new_from=payload.effective_from,
            actor=payload.created_by,
            reason=(payload.created_reason or "rollover"),
        )

        # 2) overlap check within same (jurisdiction+scenario)
        _ensure_no_overlap(
            db=db,
            jurisdiction=payload.jurisdiction,
            scenario_key=payload.scenario_key,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            exclude_id=None,
        )

        row = AppConstantsSet(
            jurisdiction=payload.jurisdiction,
            scenario_key=payload.scenario_key,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            payload=payload.payload,  # 1:1 with FE (no mutation)
            created_by=payload.created_by,
            created_reason=payload.created_reason,
            updated_by=None,
            updated_reason=None,
        )

        db.add(row)
        db.commit()
        db.refresh(row)
        return AppConstantsSetRead.model_validate(row)
    finally:
        db.close()


@router.put(
    "/admin/constants/{constants_id}",
    response_model=AppConstantsSetRead,
    summary="Admin: update postojećeg seta (bez overlap-a) u okviru scenario_key",
    operation_id="admin_constants_update",
    responses={400: {"description": "Validation / overlap error"}},
)
def admin_constants_update(constants_id: int, payload: AppConstantsSetUpdate) -> AppConstantsSetRead:
    db = _get_db()
    try:
        row = db.execute(select(AppConstantsSet).where(AppConstantsSet.id == constants_id)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Constants set not found")

        new_j = payload.jurisdiction if payload.jurisdiction is not None else row.jurisdiction
        new_s = payload.scenario_key if payload.scenario_key is not None else row.scenario_key
        new_from = payload.effective_from if payload.effective_from is not None else row.effective_from
        new_to = payload.effective_to if payload.effective_to is not None else row.effective_to

        _validate_scenario(new_j, new_s)

        _ensure_no_overlap(
            db=db,
            jurisdiction=new_j,
            scenario_key=new_s,
            effective_from=new_from,
            effective_to=new_to,
            exclude_id=row.id,
        )

        if payload.jurisdiction is not None:
            row.jurisdiction = payload.jurisdiction
        if payload.scenario_key is not None:
            row.scenario_key = payload.scenario_key
        if payload.effective_from is not None:
            row.effective_from = payload.effective_from
        if payload.effective_to is not None:
            row.effective_to = payload.effective_to

        if payload.payload is not None:
            _validate_payload_semantics(jurisdiction=new_j, payload=payload.payload)
            row.payload = payload.payload  # 1:1 with FE (no mutation)

        row.updated_by = payload.updated_by
        row.updated_reason = payload.updated_reason
        row.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(row)
        return AppConstantsSetRead.model_validate(row)
    finally:
        db.close()
