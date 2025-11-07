from __future__ import annotations

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate

router = APIRouter(tags=["tenants"])

@router.post("/tenants", status_code=201, response_model=TenantRead)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_session)):
    tid = uuid4().hex
    t = Tenant(id=tid, code=payload.code.strip(), name=payload.name.strip())
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # test dopušta 400 ili 409; vraćamo 409 da ostanemo dosljedni
        raise HTTPException(status_code=409, detail="Tenant code already exists")
    db.refresh(t)
    return TenantRead(id=t.id, code=t.code, name=t.name)

@router.get("/tenants", response_model=List[TenantRead])
def list_tenants(db: Session = Depends(get_session)):
    rows = db.execute(select(Tenant).order_by(Tenant.created_at.asc())).scalars().all()
    return [TenantRead(id=r.id, code=r.code, name=r.name) for r in rows]

@router.get("/tenants/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: str, db: Session = Depends(get_session)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantRead(id=t.id, code=t.code, name=t.name)

@router.patch("/tenants/{tenant_id}", response_model=TenantRead)
def patch_tenant(tenant_id: str, payload: TenantUpdate, db: Session = Depends(get_session)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.name is not None:
        t.name = payload.name.strip()
    db.add(t)
    db.commit()
    db.refresh(t)
    return TenantRead(id=t.id, code=t.code, name=t.name)

@router.delete("/tenants/{tenant_id}", status_code=204)
def delete_tenant(tenant_id: str, db: Session = Depends(get_session)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(t)
    db.commit()
    return None
