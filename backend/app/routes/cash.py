from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import CashEntry

router = APIRouter(prefix="/cash", tags=["cash"])


class CashCreate(BaseModel):
    entry_date: date
    # VALIDACIJA PRIJE BAZE:
    kind: Literal["income", "expense"]
    amount: Decimal = Field(gt=0)
    note: Optional[str] = None


@router.post("/")
def create_cash(
    payload: CashCreate,
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    obj = CashEntry(
        tenant_code=x_tenant_code,
        entry_date=payload.entry_date,
        kind=payload.kind,
        amount=payload.amount,
        description=payload.note,
    )
    try:
        db.add(obj)
        db.commit()
        db.refresh(obj)
    except IntegrityError as e:
        db.rollback()
        # Fallback ako ipak dođe do DB greške (npr. drugi CHECK)
        raise HTTPException(
            status_code=422,
            detail="Validation error: kind must be 'income' or 'expense', and amount > 0.",
        ) from e

    return {"id": obj.id}


@router.get("/")
def list_cash(
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    return (
        db.query(CashEntry)
        .filter(CashEntry.tenant_code == x_tenant_code)
        .order_by(CashEntry.entry_date, CashEntry.id)
        .all()
    )