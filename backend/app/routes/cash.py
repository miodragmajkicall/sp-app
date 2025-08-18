from typing import List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select

# --- DB dependency (get_session ili get_db) ---
try:
    from app.db import get_session as _get_session_dep  # preferirano
except Exception:  # pragma: no cover
    from app.db import get_db as _get_session_dep       # fallback

# --- Šeme (POST/GET/READ/PATCH) ---
from app.schemas.cash import (
    CashEntryCreate,
    CashEntryRead,
    CashEntryUpdate,
)

# --- Lazy resolver za "cash" model (izbjegavamo ImportError na importu modula) ---
import importlib

router = APIRouter(prefix="/cash", tags=["cash"])

_models_mod = importlib.import_module("app.models")
_Base = getattr(_models_mod, "Base", None)

_CASH_MODEL: Optional[Any] = None
# Kandidati po imenu klase (ako postoje)
_CANDIDATE_CLASSNAMES = ["CashEntry", "Cash", "CashModel", "CashBook", "CashRecord", "Kasa", "KnjigaKase"]
# Ključne riječi u __tablename__ ili nazivima kolona koje upućuju na “cash”
_TABLE_HINTS = ["cash", "kasa", "cashbook"]

def _resolve_cash_model() -> Any:
    global _CASH_MODEL
    if _CASH_MODEL is not None:
        return _CASH_MODEL

    # 1) Direktno po imenu
    for name in _CANDIDATE_CLASSNAMES:
        if hasattr(_models_mod, name):
            _CASH_MODEL = getattr(_models_mod, name)
            return _CASH_MODEL

    # 2) Ako imamo Base registry, pretraži mapirane modele
    if _Base is not None and hasattr(_Base, "registry") and hasattr(_Base.registry, "mappers"):
        for m in list(_Base.registry.mappers):
            cls = m.class_
            tab = getattr(cls, "__tablename__", "") or ""
            tab_l = tab.lower()
            cols = [c.key.lower() for c in getattr(m, "columns", [])] if hasattr(m, "columns") else []
            # heuristika: ime tabele sadrži "cash"/"kasa" ili ima tipične kolone
            if any(h in tab_l for h in _TABLE_HINTS) or any(k in cols for k in ["amount", "note", "direction"]):
                _CASH_MODEL = cls
                return _CASH_MODEL

    # 3) Ako ništa nije nađeno, NE ruši import aplikacije — grešku dižemo tek kada se ruta pozove
    _CASH_MODEL = None
    return None


def _get_cash_model_or_500() -> Any:
    model = _resolve_cash_model()
    if model is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Cash model not found. Tried class names: "
                + ", ".join(_CANDIDATE_CLASSNAMES)
                + " or tables with hints: "
                + ", ".join(_TABLE_HINTS)
            ),
        )
    return model


def _get_pk_column(model: Any):
    try:
        return model.__mapper__.primary_key[0]
    except Exception:
        # fallback na .id ako postoji
        if hasattr(model, "id"):
            return model.id
        raise HTTPException(status_code=500, detail="Primary key column not detected for cash model")


# ---------- Helpers ----------
def _get_cash_or_404(db: Session, cash_id: int) -> Any:
    model = _get_cash_model_or_500()
    obj = db.get(model, cash_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")
    return obj


# ---------- CRUD ----------
@router.get("/", response_model=List[CashEntryRead])
def list_cash(db: Session = Depends(_get_session_dep)) -> List[Any]:
    model = _get_cash_model_or_500()
    pk_col = _get_pk_column(model)
    stmt = select(model).order_by(pk_col.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/{cash_id}", response_model=CashEntryRead)
def get_cash(cash_id: int, db: Session = Depends(_get_session_dep)) -> Any:
    return _get_cash_or_404(db, cash_id)


@router.post("/", response_model=CashEntryRead, status_code=status.HTTP_201_CREATED)
def create_cash(payload: CashEntryCreate, db: Session = Depends(_get_session_dep)) -> Any:
    model = _get_cash_model_or_500()
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    obj = model(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{cash_id}", response_model=CashEntryRead)
def patch_cash(
    cash_id: int,
    payload: CashEntryUpdate,
    db: Session = Depends(_get_session_dep),
) -> Any:
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
    obj = _get_cash_or_404(db, cash_id)
    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
