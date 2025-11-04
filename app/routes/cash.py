# /home/miso/dev/sp-app/sp-app/app/routes/cash.py
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CashEntry, Tenant

router = APIRouter(prefix="/cash", tags=["cash"])


# -- helper: ensure tenant exists (auto-create if missing)
def ensure_tenant(db: Session, tenant_code: str) -> Tenant:
    if not tenant_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Tenant-Code header")
    tenant = db.query(Tenant).filter(Tenant.code == tenant_code).first()
    if tenant is None:
        tenant = Tenant(code=tenant_code, name=tenant_code)
        db.add(tenant)
        db.flush()  # validate FK before inserting CashEntry
    return tenant


# -- Schemas (ako već imaš u app/schemas, slobodno zamijeni importima)
class CashCreate(BaseModel):
    entry_date: date
    kind: str
    amount: Decimal
    note: Optional[str] = Field(None, alias="description")

    class Config:
        populate_by_name = True


class CashRead(BaseModel):
    id: int
    tenant_code: str
    entry_date: date
    kind: str
    amount: Decimal
    description: Optional[str]
    created_at: Optional[str]


@router.get("/", response_model=List[CashRead])
def list_cash(
    db: Session = Depends(get_db),
    x_tenant_code: Optional[str] = Header(default=None, convert_underscores=False),
):
    if not x_tenant_code:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Code header")
    return (
        db.query(CashEntry)
        .filter(CashEntry.tenant_code == x_tenant_code)
        .order_by(CashEntry.created_at.desc())
        .all()
    )


@router.post("/", status_code=200)
def create_cash(
    payload: CashCreate,
    db: Session = Depends(get_db),
    x_tenant_code: Optional[str] = Header(default=None, convert_underscores=False),
):
    ensure_tenant(db, x_tenant_code)

    description = payload.note if payload.note is not None else payload.__dict__.get("description")

    entry = CashEntry(
        tenant_code=x_tenant_code,
        entry_date=payload.entry_date,
        kind=payload.kind,
        amount=payload.amount,
        description=description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}
