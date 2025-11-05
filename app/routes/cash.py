from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Literal, Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import CashEntry
from ..schemas.cash import CashEntryRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cash", tags=["cash"])


class CashCreate(BaseModel):
    entry_date: date
    kind: Literal["income", "expense"]
    amount: Decimal = Field(gt=0)
    note: Optional[str] = None


@router.post("/", response_model=CashEntryRead, response_model_exclude_none=True)
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
        db.flush()     # osiguraj ID prije refresh-a u istom transakcijskom kontekstu
        db.refresh(obj)
    except IntegrityError as e:
        # transakcija će pasti u except u get_session i uraditi rollback
        raise HTTPException(
            status_code=422,
            detail="Validation error: kind must be 'income' or 'expense', and amount > 0.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error on insert: %s", e)
        raise HTTPException(status_code=500, detail="Insert failed.") from e

    return CashEntryRead.model_validate(obj)


@router.get("/", response_model=List[CashEntryRead], response_model_exclude_none=True)
def list_cash(
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    rows = (
        db.query(CashEntry)
        .filter(CashEntry.tenant_code == x_tenant_code)
        .order_by(CashEntry.entry_date, CashEntry.id)
        .all()
    )
    return [CashEntryRead.model_validate(r) for r in rows]
