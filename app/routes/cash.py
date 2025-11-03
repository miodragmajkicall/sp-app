from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry
from app.schemas.cash import CashEntryCreate, CashEntryRead, CashEntryUpdate

router = APIRouter(prefix="/cash", tags=["cash"])


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    if not x_tenant_code:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Code header")
    return x_tenant_code


@router.get("/", response_model=List[CashEntryRead])
def list_cash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None),
) -> List[CashEntry]:
    tenant = _require_tenant(x_tenant_code)
    stmt = (
        select(CashEntry)
        .where(CashEntry.tenant_code == tenant)
        .order_by(CashEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/{cash_id}", response_model=CashEntryRead)
def get_cash(
    cash_id: str,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None),
) -> CashEntry:
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id, CashEntry.tenant_code == tenant
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")
    return obj


@router.post("/", response_model=CashEntryRead, status_code=status.HTTP_201_CREATED)
def create_cash(
    payload: CashEntryCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None),
) -> CashEntry:
    tenant = _require_tenant(x_tenant_code)
    data = payload.model_dump()
    data.setdefault("tenant_code", tenant)
    data.setdefault("created_at", datetime.now(timezone.utc))
    obj = CashEntry(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{cash_id}", response_model=CashEntryRead)
def patch_cash(
    cash_id: str,
    payload: CashEntryUpdate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None),
) -> CashEntry:
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id, CashEntry.tenant_code == tenant
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{cash_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cash(
    cash_id: str,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None),
) -> Response:
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id, CashEntry.tenant_code == tenant
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")

    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
