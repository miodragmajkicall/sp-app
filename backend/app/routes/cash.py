# backend/app/routes/cash.py
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session

# Pokušaj modela iz app.models (primarni), a fallback na app.models_cash ako tako postoji
try:
    from app.models import CashEntry
except Exception:  # pragma: no cover
    from app.models_cash import CashEntry  # type: ignore

# Ako već imaš Pydantic šeme u app/schemas/cash.py, koristimo njih
try:
    from app.schemas.cash import CashEntryCreate, CashEntryRead  # type: ignore
    USE_SCHEMAS = True
except Exception:
    # Minimalni fallback ako šeme ne postoje (neće se koristiti ako gornji import prođe)
    from pydantic import BaseModel, ConfigDict
    from typing import Optional

    class CashEntryCreate(BaseModel):
        amount: float
        note: Optional[str] = None

    class CashEntryRead(BaseModel):
        model_config = ConfigDict(from_attributes=True)
        id: int
        amount: float
        note: Optional[str] = None

    USE_SCHEMAS = False

router = APIRouter(prefix="/cash", tags=["cash"])


@router.post(
    "",
    response_model=CashEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_cash(
    payload: CashEntryCreate,
    db: Session = Depends(get_session),
) -> CashEntryRead:
    """
    Kreira cash entry i vraća 201 + JSON sa `id` na rootu (i ostalim poljima).
    """
    try:
        obj = CashEntry(**payload.model_dump())
        db.add(obj)
        db.flush()   # dobijamo obj.id bez dodatnog selecta
        db.refresh(obj)
        return obj  # FastAPI + Pydantic v2 će serializirati iz ORM-a (from_attributes=True)
    except Exception as e:  # pragma: no cover
        db.rollback()
        raise HTTPException(status_code=400, detail=f"cash create failed: {e!r}")


@router.get("", response_model=list[CashEntryRead])
def list_cash(db: Session = Depends(get_session)) -> list[CashEntryRead]:
    """
    Jednostavan listing (opcionalno, čisto da ne izgubimo postojeću funkcionalnost).
    """
    q = db.query(CashEntry).order_by(CashEntry.id.desc()).limit(50)
    return list(q)
