# /home/miso/dev/sp-app/sp-app/backend/app/routes/admin_constants.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, or_, select
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


# ======================================================
#  DB helper
# ======================================================
def _get_db() -> Session:
    return SessionLocal()


def _ranges_overlap(
    *,
    a_from: date,
    a_to: Optional[date],
    b_from: date,
    b_to: Optional[date],
) -> bool:
    """
    Intervali su zatvoreni: [from, to], a None znači "beskonačno".
    Overlap:
      a_from <= b_to (ili b_to None) AND b_from <= a_to (ili a_to None)
    """
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


def _find_current_set(
    *,
    db: Session,
    jurisdiction: str,
    as_of: date,
) -> Optional[AppConstantsSet]:
    """
    Vraća set koji je aktivan na datum `as_of`:
      effective_from <= as_of AND (effective_to IS NULL OR effective_to >= as_of)
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
    return db.execute(stmt).scalar_one_or_none()


# ======================================================
#  ADMIN: LIST
# ======================================================
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


# ======================================================
#  ADMIN: CREATE
# ======================================================
@router.post(
    "/admin/constants",
    response_model=AppConstantsSetRead,
    summary="Admin: kreiraj novi set konstanti (bez overlap-a)",
    operation_id="admin_constants_create",
    responses={400: {"description": "Validation / overlap error"}},
)
def admin_constants_create(payload: AppConstantsSetCreate) -> AppConstantsSetRead:
    db = _get_db()
    try:
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
        # updated_at server_default postoji; ostavljamo na insert.
        db.add(row)
        db.commit()
        db.refresh(row)
        return AppConstantsSetRead.model_validate(row)
    finally:
        db.close()


# ======================================================
#  ADMIN: UPDATE
# ======================================================
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


# ======================================================
#  PUBLIC: CURRENT
# ======================================================
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
