from __future__ import annotations

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate

# Napomena:
# "Tenant" predstavlja jednog klijenta / poslovni subjekt u sistemu (npr. frizerski salon,
# pekaru, obrt...). Svi njegovi podaci (cash unosi, fakture, izvještaji)
# se logički vežu za taj tenant preko polja `tenant_code` ili `tenant_id`.

router = APIRouter(tags=["tenants"])


@router.post(
    "/tenants",
    status_code=status.HTTP_201_CREATED,
    response_model=TenantRead,
    summary="Kreiranje novog tenanta",
    description=(
        "Kreira novog tenanta (klijenta aplikacije) na osnovu prosleđenog `code` i `name`.\n\n"
        "- `code` mora biti jedinstven u sistemu.\n"
        "- U slučaju duplikata, vraća se HTTP 409 (Tenant code already exists)."
    ),
)
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


@router.get(
    "/tenants",
    response_model=List[TenantRead],
    summary="Lista svih tenanata",
    description=(
        "Vraća listu svih registrovanih tenanata, sortiranu po `created_at` uzlazno.\n\n"
        "Ovaj endpoint je koristan za administraciju i pregled svih klijenata u sistemu."
    ),
)
def list_tenants(db: Session = Depends(get_session)):
    rows = db.execute(select(Tenant).order_by(Tenant.created_at.asc())).scalars().all()
    return [TenantRead(id=r.id, code=r.code, name=r.name) for r in rows]


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    summary="Detalji jednog tenanta",
    description=(
        "Vraća detalje jednog tenanta na osnovu njegovog `id` polja.\n\n"
        "Ako tenant ne postoji, vraća HTTP 404 (Tenant not found)."
    ),
)
def get_tenant(tenant_id: str, db: Session = Depends(get_session)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantRead(id=t.id, code=t.code, name=t.name)


@router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    summary="Djelimično ažuriranje tenanta",
    description=(
        "Djelimično ažurira postojeći tenant.\n\n"
        "Trenutno je omogućeno ažuriranje `name` polja. "
        "Ako tenant ne postoji, vraća HTTP 404."
    ),
)
def patch_tenant(
    tenant_id: str,
    payload: TenantUpdate,
    db: Session = Depends(get_session),
):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.name is not None:
        t.name = payload.name.strip()
    db.add(t)
    db.commit()
    db.refresh(t)
    return TenantRead(id=t.id, code=t.code, name=t.name)


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje tenanta",
    description=(
        "Briše tenanta iz sistema na osnovu `tenant_id`.\n\n"
        "Ako tenant ne postoji, vraća HTTP 404. "
        "Uspješno brisanje vraća HTTP 204 (No Content) bez tijela odgovora."
    ),
)
def delete_tenant(tenant_id: str, db: Session = Depends(get_session)):
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(t)
    db.commit()
    return None
