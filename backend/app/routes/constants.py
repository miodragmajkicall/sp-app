# /home/miso/dev/sp-app/sp-app/backend/app/routes/constants.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AppConstantsSet
from app.schemas.constants import (
    ALLOWED_SCENARIOS,
    AppConstantsCurrentResponse,
    AppConstantsSetRead,
)

router = APIRouter(tags=["constants"])


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


@router.get(
    "/constants/current",
    response_model=AppConstantsCurrentResponse,
    summary="Vraća trenutno važeći set konstanti za jurisdikciju, scenario i datum",
    operation_id="constants_current",
)
def constants_current(
    jurisdiction: str = Query(..., description="RS / FBiH / BD"),
    scenario_key: str = Query(..., description="scenario_key (npr. rs_primary)"),
    as_of: date = Query(..., description="Datum za koji tražimo važeći set (YYYY-MM-DD)"),
) -> AppConstantsCurrentResponse:
    db = _get_db()
    try:
        _validate_scenario(jurisdiction, scenario_key)
        row = _find_current_set(db=db, jurisdiction=jurisdiction, scenario_key=scenario_key, as_of=as_of)
        if row is None:
            return AppConstantsCurrentResponse(
                jurisdiction=jurisdiction,
                scenario_key=scenario_key,
                as_of=as_of,
                found=False,
                item=None,
            )
        return AppConstantsCurrentResponse(
            jurisdiction=jurisdiction,
            scenario_key=scenario_key,
            as_of=as_of,
            found=True,
            item=AppConstantsSetRead.model_validate(row),
        )
    finally:
        db.close()
