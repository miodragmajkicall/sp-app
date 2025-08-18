from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select

# --- Fallback za dependency iz db modula ---
# Neka instalacije koriste get_session, neke get_db; podržimo obje bez mijenjanja db.py
try:
    from app.db import get_session as _get_session_dep  # preferirano ime
except Exception:  # pragma: no cover
    from app.db import get_db as _get_session_dep  # fallback

from app.models import CashEntry
from app.schemas.cash import (
    CashEntryCreate,
    CashEntryRead,
    CashEntryUpdate,
)

router = APIRouter(prefix="/cash", tags=["cash"])


# ---------- Helpers ----------
def _get_cash_or_404(db: Session, cash_id: int) -> CashEntry:
    obj = db.get(CashEntry, cash_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")
    return obj


# ---------- CRUD ----------
@router.get("/", response_model=List[CashEntryRead])
def list_cash(db: Session = Depends(_get_session_dep)) -> List[CashEntry]:
    """Lista svih zapisa (po ID silazno)."""
    stmt = select(CashEntry).order_by(CashEntry.id.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/{cash_id}", response_model=CashEntryRead)
def get_cash(cash_id: int, db: Session = Depends(_get_session_dep)) -> CashEntry:
    """Vraća jedan zapis po ID-u."""
    return _get_cash_or_404(db, cash_id)


@router.post("/", response_model=CashEntryRead, status_code=status.HTTP_201_CREATED)
def create_cash(payload: CashEntryCreate, db: Session = Depends(_get_session_dep)) -> CashEntry:
    """Kreira novi zapis."""
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    obj = CashEntry(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{cash_id}", response_model=CashEntryRead)
def patch_cash(
    cash_id: int,
    payload: CashEntryUpdate,
    db: Session = Depends(_get_session_dep),
) -> CashEntry:
    """
    Parcijalna izmjena (PATCH).
    - Dozvoljava slanje samo dijela polja (npr. amount/note).
    - Nepoznata polja se ignorišu zahvaljujući `extra="allow"` u šemi.
    """
    obj = _get_cash_or_404(db, cash_id)
    data = (
        payload.model_dump(exclude_unset=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_unset=True)
    )
    for k, v in data.items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{cash_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cash(cash_id: int, db: Session = Depends(_get_session_dep)) -> Response:
    """Briše zapis (204 No Content ako je uspjelo)."""
    obj = _get_cash_or_404(db, cash_id)
    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
