# app/routes/cash.py
from __future__ import annotations

import uuid
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
    """Obavezno prisustvo tenant headera."""
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
    """
    Ključna promjena: ako payload sadrži `tenant_code: null` (ili ga nema),
    **PREPISUJEMO** vrijednost iz headera umjesto setdefault (koji ne radi kad je ključ prisutan s None).
    Takođe generišemo `id` ako nije poslan i `created_at` ako nije popunjen.
    """
    tenant = _require_tenant(x_tenant_code)

    data = payload.model_dump()

    # Forsiraj tenant iz headera ako nema ili je None/prazno u payloadu
    if not data.get("tenant_code"):
        data["tenant_code"] = tenant

    # Generiši id ako nije dat (izbjeći SAWarning za PK bez generatora)
    if not data.get("id"):
        data["id"] = str(uuid.uuid4())

    # Postavi created_at ako nije dat
    if not data.get("created_at"):
        data["created_at"] = datetime.now(timezone.utc)

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
