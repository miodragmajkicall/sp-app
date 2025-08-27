from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import CashEntry
from app.schemas.cash import CashEntryCreate, CashEntryRead

router = APIRouter(prefix="/cash", tags=["cash"])


def _normalize_kind(v: str) -> str:
    k = (v or "").strip().lower()
    mapping = {"income": "income", "expense": "expense", "in": "income", "out": "expense"}
    if k not in mapping:
        raise HTTPException(status_code=422, detail="kind must be income/expense (or IN/OUT)")
    return mapping[k]


@router.post("/", response_model=CashEntryRead, status_code=status.HTTP_201_CREATED)
def create_cash(
    payload: CashEntryCreate,
    db: Session = Depends(get_session),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
):
    tenant = (x_tenant_code or "public").strip()
    if not tenant:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Code header")

    obj = CashEntry(
        tenant_code=tenant,
        entry_date=payload.entry_date,
        kind=_normalize_kind(payload.kind),
        amount=payload.amount,
        created_at=datetime.now(timezone.utc),
        description=None,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"DB error: {e.__class__.__name__}") from e
    db.refresh(obj)
    return obj


@router.get("/{cash_id}", response_model=CashEntryRead)
def get_cash_entry(
    cash_id: int,
    db: Session = Depends(get_session),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
):
    _ = (x_tenant_code or "public").strip()
    obj = db.get(CashEntry, cash_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj
