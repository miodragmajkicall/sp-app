# /home/miso/dev/sp-app/sp-app/app/routes/cash.py
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from decimal import Decimal

from ..db import get_session
from ..models import CashEntry
from ..schemas.cash import (
    CashEntryCreate,
    CashEntryRead,
    CashEntryUpdate,
    CashSummaryRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cash", tags=["cash"])

# --- Shared OpenAPI examples -------------------------------------------------

_example_tenant_header = {"X-Tenant-Code": {"example": "t-demo"}}

_post_openapi = {
    "requestBody": {
        "content": {
            "application/json": {
                "examples": {
                    "income_simple": {
                        "summary": "Income (sa aliasima date/note)",
                        "value": {
                            "date": "2025-11-06",
                            "amount": 77.7,
                            "kind": "INCOME",
                            "note": "alias test"
                        },
                    },
                    "expense_verbose": {
                        "summary": "Expense (bez aliasa)",
                        "value": {
                            "entry_date": "2025-11-06",
                            "amount": "50.00",
                            "kind": "expense",
                            "description": "kupovina papira"
                        },
                    },
                }
            }
        }
    }
}

_patch_openapi = {
    "requestBody": {
        "content": {
            "application/json": {
                "examples": {
                    "update_note_amount": {
                        "summary": "Promijeni bilješku i iznos (alias note)",
                        "value": {
                            "note": "updated via PATCH",
                            "amount": 200.5
                        },
                    },
                    "update_date_kind": {
                        "summary": "Promijeni datum i tip (alias date, UPPERCASE kind)",
                        "value": {
                            "date": "2025-11-07",
                            "kind": "EXPENSE"
                        },
                    },
                }
            }
        }
    }
}


@router.post(
    "/",
    response_model=CashEntryRead,
    response_model_exclude_none=True,
    summary="Create cash entry",
    description=(
        "Kreira novi cash zapis za **tenant** iz zaglavlja `X-Tenant-Code`.\n\n"
        "- Input podržava **alias polja**: `date` → `entry_date`, `note` → `description`.\n"
        "- `kind` je **case-insensitive** (`income`/`expense`).\n"
        "- `amount` se normalizuje na 2 decimale."
    ),
    openapi_extra=_post_openapi,
)
def create_cash(
    payload: CashEntryCreate,
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    obj = CashEntry(
        tenant_code=x_tenant_code,
        entry_date=payload.entry_date,
        kind=payload.kind,
        amount=payload.amount,
        description=payload.description,
    )
    try:
        db.add(obj)
        db.flush()   # dobij ID u okviru iste transakcije
        db.refresh(obj)
    except IntegrityError as e:
        raise HTTPException(
            status_code=422,
            detail="Validation error while inserting cash entry.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error on insert: %s", e)
        raise HTTPException(status_code=500, detail="Insert failed.") from e

    return CashEntryRead.model_validate(obj)


@router.get(
    "/",
    response_model=List[CashEntryRead],
    response_model_exclude_none=True,
    summary="List cash entries",
    description="Vraća listu svih zapisa za dati tenant (`X-Tenant-Code`). Sortirano po `entry_date`, pa `id`.",
)
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


@router.get(
    "/{entry_id}",
    response_model=CashEntryRead,
    response_model_exclude_none=True,
    summary="Get cash entry by id",
    description="Dohvata jedan zapis po `id` unutar tenanta (`X-Tenant-Code`). Vraća **404** ako ne postoji.",
)
def get_cash_by_id(
    entry_id: int = Path(..., ge=1),
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    obj = (
        db.query(CashEntry)
        .filter(
            CashEntry.tenant_code == x_tenant_code,
            CashEntry.id == entry_id,
        )
        .one_or_none()
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Cash entry not found for tenant.")
    return CashEntryRead.model_validate(obj)


class DeleteResultModel(BaseModel):
    id: int
    deleted: bool


@router.delete(
    "/{entry_id}",
    response_model=DeleteResultModel,
    status_code=status.HTTP_200_OK,
    summary="Delete cash entry",
    description="Briše jedan zapis po `id` unutar tenanta (`X-Tenant-Code`). Vraća **404** ako ne postoji.",
)
def delete_cash_by_id(
    entry_id: int = Path(..., ge=1),
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    obj = (
        db.query(CashEntry)
        .filter(
            CashEntry.tenant_code == x_tenant_code,
            CashEntry.id == entry_id,
        )
        .one_or_none()
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Cash entry not found for tenant.")

    db.delete(obj)
    db.flush()  # pošalji DELETE odmah
    return DeleteResultModel(id=entry_id, deleted=True)


@router.patch(
    "/{entry_id}",
    response_model=CashEntryRead,
    response_model_exclude_none=True,
    summary="Patch cash entry",
    description=(
        "Parcijalno ažurira zapis po `id` unutar tenanta (`X-Tenant-Code`).\n\n"
        "Dozvoljena polja: `date|entry_date`, `amount`, `kind` (case-insensitive), `note|description`."
    ),
    openapi_extra=_patch_openapi,
)
def patch_cash_by_id(
    entry_id: int = Path(..., ge=1),
    payload: CashEntryUpdate = ...,
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
):
    obj = (
        db.query(CashEntry)
        .filter(
            CashEntry.tenant_code == x_tenant_code,
            CashEntry.id == entry_id,
        )
        .one_or_none()
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Cash entry not found for tenant.")

    if payload.entry_date is not None:
        obj.entry_date = payload.entry_date
    if payload.amount is not None:
        obj.amount = payload.amount
    if payload.kind is not None:
        obj.kind = payload.kind
    if payload.description is not None:
        obj.description = payload.description

    try:
        db.flush()
        db.refresh(obj)
    except IntegrityError as e:
        raise HTTPException(status_code=422, detail="Validation error on update.") from e
    except Exception as e:
        logger.exception("Unexpected error on update: %s", e)
        raise HTTPException(status_code=500, detail="Update failed.") from e

    return CashEntryRead.model_validate(obj)


@router.get(
    "/summary",
    response_model=CashSummaryRead,
    summary="Cash summary (income, expense, net, counts)",
    description=(
        "Vraća zbirne iznose i brojeve zapisa za dati tenant. "
        "Opcioni query parametri `from` i `to` (YYYY-MM-DD) ograničavaju interval po `entry_date`."
    ),
)
def cash_summary(
    db: Session = Depends(get_session),
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    # priprema baznog query-ja sa tenant scopingom
    q = db.query(
        CashEntry.kind,
        func.count(CashEntry.id).label("cnt"),
        func.coalesce(func.sum(CashEntry.amount), 0).label("total"),
    ).filter(CashEntry.tenant_code == x_tenant_code)

    # opcioni datumski filteri
    if from_date:
        q = q.filter(CashEntry.entry_date >= from_date)
    if to_date:
        q = q.filter(CashEntry.entry_date <= to_date)

    rows = q.group_by(CashEntry.kind).all()

    income_total = Decimal("0.00")
    expense_total = Decimal("0.00")
    income_count = 0
    expense_count = 0

    for kind, cnt, total in rows:
        if kind == "income":
            income_total = Decimal(str(total)).quantize(Decimal("0.01"))
            income_count = int(cnt or 0)
        elif kind == "expense":
            expense_total = Decimal(str(total)).quantize(Decimal("0.01"))
            expense_count = int(cnt or 0)

    net_total = (income_total - expense_total).quantize(Decimal("0.01"))

    return CashSummaryRead(
        tenant_code=x_tenant_code,
        from_date=from_date,  # FastAPI konvertuje u date u OpenAPI-u; ovdje ih vraćamo kao string/date kompatibilno
        to_date=to_date,
        income_total=income_total,
        expense_total=expense_total,
        net_total=net_total,
        income_count=income_count,
        expense_count=expense_count,
    )
