from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Tenant
from app.schemas.cash import (
    CashEntryCreate,
    CashEntryRead,
    CashEntryUpdate,
    CashSummaryRead,
)

router = APIRouter(prefix="/cash", tags=["cash"])


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    if not x_tenant_code:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Code header")
    return x_tenant_code


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Pobrini se da u bazi postoji red u tenants sa zadatim code.

    - Ako tenant već postoji: ne radi ništa.
    - Ako ne postoji: kreira se minimalni tenant sa:
        id = code (odrezan na 32 karaktera)
        code = prosleđeni kod
        name = "Tenant {code}"
    """
    stmt = select(Tenant).where(Tenant.code == code)
    existing = db.execute(stmt).scalars().first()
    if existing:
        return

    tenant = Tenant(
        id=code[:32],  # Tenant.id je String(32) → kratimo ako je duže
        code=code,
        name=f"Tenant {code}",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)


@router.get("/summary", response_model=CashSummaryRead)
def get_cash_summary(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum filtera (YYYY-MM-DD, uključivo).",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum filtera (YYYY-MM-DD, uključivo).",
    ),
) -> CashSummaryRead:
    """
    Vraća zbir prihoda, rashoda i neto rezultat za zadatog tenanta i opcioni datumski opseg.
    """
    tenant = _require_tenant(x_tenant_code)

    income_expr = func.coalesce(
        func.sum(
            case(
                (CashEntry.kind == "income", CashEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    expense_expr = func.coalesce(
        func.sum(
            case(
                (CashEntry.kind == "expense", CashEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    stmt = select(income_expr.label("income"), expense_expr.label("expense")).where(
        CashEntry.tenant_code == tenant
    )

    if date_from is not None:
        stmt = stmt.where(CashEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CashEntry.entry_date <= date_to)

    row = db.execute(stmt).one()
    income, expense = row.income, row.expense
    net = income - expense

    return CashSummaryRead(income=income, expense=expense, net=net)


@router.get("/", response_model=List[CashEntryRead])
def list_cash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> List[CashEntry]:
    tenant = _require_tenant(x_tenant_code)
    stmt = (
        select(CashEntry)
        .where(CashEntry.tenant_code == tenant)
        .order_by(CashEntry.created_at.desc(), CashEntry.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/{cash_id}", response_model=CashEntryRead)
def get_cash(
    cash_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> CashEntry:
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id,
        CashEntry.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")
    return obj


@router.post("/", response_model=CashEntryRead, status_code=status.HTTP_201_CREATED)
def create_cash(
    payload: CashEntryCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> CashEntry:
    tenant = _require_tenant(x_tenant_code)

    # Prvo osiguramo da postoji odgovarajući tenant u tabeli tenants,
    # kako bi FK cash_entries.tenant_code → tenants.code prošao.
    _ensure_tenant_exists(db, tenant)

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
    cash_id: int,
    payload: CashEntryUpdate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> CashEntry:
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id,
        CashEntry.tenant_code == tenant,
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
    cash_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> Response:
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id,
        CashEntry.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")

    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
