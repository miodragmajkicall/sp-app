# /home/miso/dev/sp-app/sp-app/backend/app/routes/admin_constants.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AppConstantsSet
from app.schemas.constants import (
    AppConstantsSetCreate,
    AppConstantsSetRead,
    AppConstantsSetUpdate,
    AppConstantsSetListResponse,
    AppConstantsCurrentResponse,
)

router = APIRouter(tags=["admin"])


def _get_db() -> Session:
    return SessionLocal()


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
    effective_from: date,
    effective_to: Optional[date],
    exclude_id: Optional[int] = None,
) -> None:
    stmt = select(AppConstantsSet).where(AppConstantsSet.jurisdiction == jurisdiction)
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
                    "Overlapping effective date range for this jurisdiction. "
                    f"Conflicts with id={row.id} [{row.effective_from}..{row.effective_to}]"
                ),
            )


def _find_current_set(*, db: Session, jurisdiction: str, as_of: date) -> Optional[AppConstantsSet]:
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
    return db.execute(stmt).scalar_one_or_none()


def _rollover_close_previous_if_needed(
    *,
    db: Session,
    jurisdiction: str,
    new_from: date,
    actor: Optional[str],
    reason: str,
) -> None:
    """
    Rollover samo za open-ended prethodni set (effective_to IS NULL):
    - Ako postoji aktivan open-ended set na new_from, zatvori ga na (new_from - 1 dan).
    - Ako je prethodni set već imao effective_to (zatvoren period), NE diramo ga (overlap ide na 400).
    """
    prev = _find_current_set(db=db, jurisdiction=jurisdiction, as_of=new_from)
    if prev is None:
        return

    # Ključna promjena: rollover samo ako je prev open-ended
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


@router.get(
    "/admin/constants",
    response_model=AppConstantsSetListResponse,
    summary="Admin: list setova zakonskih konstanti (effective-dated) po jurisdikciji",
    operation_id="admin_constants_list",
)
def admin_constants_list(
    jurisdiction: Optional[str] = Query(None, description="RS / FBiH / BD"),
) -> AppConstantsSetListResponse:
    db = _get_db()
    try:
        stmt = select(AppConstantsSet).order_by(
            AppConstantsSet.jurisdiction.asc(),
            AppConstantsSet.effective_from.desc(),
            AppConstantsSet.id.desc(),
        )
        if jurisdiction:
            stmt = stmt.where(AppConstantsSet.jurisdiction == jurisdiction)

        rows = db.execute(stmt).scalars().all()
        items = [AppConstantsSetRead.model_validate(r) for r in rows]
        return AppConstantsSetListResponse(items=items)
    finally:
        db.close()


@router.post(
    "/admin/constants",
    response_model=AppConstantsSetRead,
    summary="Admin: kreiraj novi set konstanti (rollover zatvara samo open-ended prethodni set)",
    operation_id="admin_constants_create",
    responses={400: {"description": "Validation / overlap error"}},
)
def admin_constants_create(payload: AppConstantsSetCreate) -> AppConstantsSetRead:
    db = _get_db()
    try:
        # 1) Rollover samo ako postoji open-ended set
        _rollover_close_previous_if_needed(
            db=db,
            jurisdiction=payload.jurisdiction,
            new_from=payload.effective_from,
            actor=payload.created_by,
            reason=(payload.created_reason or "rollover"),
        )

        # 2) Zatim overlap provjera (sad će i dalje baciti 400 za bounded overlap slučajeve)
        _ensure_no_overlap(
            db=db,
            jurisdiction=payload.jurisdiction,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            exclude_id=None,
        )

        row = AppConstantsSet(
            jurisdiction=payload.jurisdiction,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            payload=payload.payload,
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
    summary="Admin: update postojećeg seta (bez overlap-a)",
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
        new_from = payload.effective_from if payload.effective_from is not None else row.effective_from
        new_to = payload.effective_to if payload.effective_to is not None else row.effective_to

        _ensure_no_overlap(
            db=db,
            jurisdiction=new_j,
            effective_from=new_from,
            effective_to=new_to,
            exclude_id=row.id,
        )

        if payload.jurisdiction is not None:
            row.jurisdiction = payload.jurisdiction
        if payload.effective_from is not None:
            row.effective_from = payload.effective_from
        if payload.effective_to is not None:
            row.effective_to = payload.effective_to
        if payload.payload is not None:
            row.payload = payload.payload

        row.updated_by = payload.updated_by
        row.updated_reason = payload.updated_reason
        row.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(row)
        return AppConstantsSetRead.model_validate(row)
    finally:
        db.close()


@router.get(
    "/constants/current",
    response_model=AppConstantsCurrentResponse,
    summary="Vraća trenutno važeći set konstanti za jurisdikciju i datum",
    operation_id="constants_current",
)
def constants_current(
    jurisdiction: str = Query(..., description="RS / FBiH / BD"),
    as_of: date = Query(..., description="Datum za koji tražimo važeći set (YYYY-MM-DD)"),
) -> AppConstantsCurrentResponse:
    db = _get_db()
    try:
        row = _find_current_set(db=db, jurisdiction=jurisdiction, as_of=as_of)
        if row is None:
            return AppConstantsCurrentResponse(
                jurisdiction=jurisdiction,
                as_of=as_of,
                found=False,
                item=None,
            )
        return AppConstantsCurrentResponse(
            jurisdiction=jurisdiction,
            as_of=as_of,
            found=True,
            item=AppConstantsSetRead.model_validate(row),
        )
    finally:
        db.close()
