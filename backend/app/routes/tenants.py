from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from app.db import get_db
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    t = Tenant(code=payload.code, name=payload.name)
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="code already exists")
    db.refresh(t)
    return t

@router.get("", response_model=List[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    rows = db.execute(select(Tenant).order_by(Tenant.created_at.desc())).scalars().all()
    return rows
from uuid import UUID

@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant not found")
    return t

@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: UUID, payload: TenantUpdate, db: Session = Depends(get_db)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant not found")

    if payload.code is not None:
        t.code = payload.code
    if payload.name is not None:
        t.name = payload.name

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="code already exists")
    db.refresh(t)
    return t

