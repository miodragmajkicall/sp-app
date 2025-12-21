# /home/miso/dev/sp-app/sp-app/backend/app/routes/constants.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.schemas.constants import ConstantsCurrentRead

# NOTE:
# AppConstantsSet model dodajemo u models.py u sljedećoj isporuci.
# from app.models import AppConstantsSet

router = APIRouter(
    tags=["constants"],
)


@router.get(
    "/constants/current",
    response_model=ConstantsCurrentRead,
    summary="Aktivni set zakonskih konstanti za entitet i datum",
    description=(
        "Vraća trenutno važeći set konstanti za dati `jurisdiction` (RS/FBiH/BD).\n\n"
        "- `on_date` je opciono; ako nije poslan, koristi se današnji datum.\n"
        "- Ako ne postoji važeći set → HTTP 404."
    ),
    operation_id="constants_current_get",
)
def get_current_constants(
    jurisdiction: str = Query(..., examples=["RS", "FBiH", "BD"]),
    on_date: Optional[date] = Query(None, description="Datum za koji se traži važeći set."),
    db: Session = Depends(_get_session_dep),
) -> ConstantsCurrentRead:
    # Lazy import da ne rušimo app dok ne dodamo model.
    from app.models import AppConstantsSet  # pylint: disable=import-error

    d = on_date or date.today()

    stmt = (
        select(AppConstantsSet)
        .where(
            and_(
                AppConstantsSet.jurisdiction == jurisdiction,
                AppConstantsSet.effective_from <= d,
                or_(
                    AppConstantsSet.effective_to.is_(None),
                    AppConstantsSet.effective_to >= d,
                ),
            )
        )
        .order_by(AppConstantsSet.effective_from.desc(), AppConstantsSet.id.desc())
        .limit(1)
    )

    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active constants set for jurisdiction={jurisdiction} on_date={d.isoformat()}",
        )

    return ConstantsCurrentRead.model_validate(row)
