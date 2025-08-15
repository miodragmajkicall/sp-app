# backend/app/routes/cash.py
from datetime import date
from typing import Optional
from uuid import uuid4


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db                         # <- ako se drugačije zove, prilagodi
from ..schemas.cash import (
    CashEntryCreate, CashEntryRead, CashEntryUpdate,
    CashList, CashSummary
)

router = APIRouter(prefix="/cash", tags=["cash"])

@router.get("/health")
def cash_health():
    return {"cash": "ok"}

# CREATE
@router.post("/entries", response_model=CashEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: CashEntryCreate, db: Session = Depends(get_db)):
    eid = str(uuid4())
    params = {**payload.model_dump(), "id": eid}
    q = text("""
        INSERT INTO cash_entries (id, tenant_code, entry_date, kind, amount, description)
        VALUES (:id, :tenant_code, :entry_date, :kind, :amount, :description)
        RETURNING id, tenant_code, entry_date, kind, amount, description, created_at
    """)
    row = db.execute(q, params).mappings().one()
    db.commit()
    return row


# LIST (sa filtrima i paginacijom)
@router.get("/entries", response_model=CashList)
def list_entries(
    tenant: str = Query(..., min_length=1, max_length=64),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    where = ["tenant_code = :tenant"]
    params: dict = {"tenant": tenant, "limit": limit, "offset": offset}
    if date_from:
        where.append("entry_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("entry_date <= :date_to")
        params["date_to"] = date_to
    where_sql = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT id, tenant_code, entry_date, kind, amount, description, created_at
        FROM cash_entries
        WHERE {where_sql}
        ORDER BY entry_date DESC, created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    total = db.execute(text(f"""
        SELECT count(*) AS c
        FROM cash_entries
        WHERE {where_sql}
    """), params).scalar_one()

    return {"items": rows, "total": int(total)}

# GET by id
@router.get("/entries/{entry_id}", response_model=CashEntryRead)
def get_entry(entry_id: str, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT id, tenant_code, entry_date, kind, amount, description, created_at
        FROM cash_entries WHERE id = :id
    """), {"id": entry_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row

# UPDATE (partial)
@router.patch("/entries/{entry_id}", response_model=CashEntryRead)
def update_entry(entry_id: str, payload: CashEntryUpdate, db: Session = Depends(get_db)):
    data = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not data:
        return get_entry(entry_id, db)

    sets = []
    for key in data.keys():
        sets.append(f"{key} = :{key}")
    data["id"] = entry_id

    row = db.execute(text(f"""
        UPDATE cash_entries
        SET {", ".join(sets)}
        WHERE id = :id
        RETURNING id, tenant_code, entry_date, kind, amount, description, created_at
    """), data).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    db.commit()
    return row

# DELETE
@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: str, db: Session = Depends(get_db)):
    n = db.execute(text("DELETE FROM cash_entries WHERE id = :id"), {"id": entry_id}).rowcount
    db.commit()
    if n == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return None

# MJESEČNI REZIME
@router.get("/summary", response_model=CashSummary)
def monthly_summary(
    tenant: str = Query(..., min_length=1, max_length=64),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    q = text("""
        SELECT
          :tenant     AS tenant_code,
          :year       AS year,
          :month      AS month,
          COALESCE(SUM(CASE WHEN kind='income' THEN amount END), 0) AS income,
          COALESCE(SUM(CASE WHEN kind='expense' THEN amount END), 0) AS expense
        FROM cash_entries
        WHERE tenant_code = :tenant
          AND EXTRACT(YEAR FROM entry_date) = :year
          AND EXTRACT(MONTH FROM entry_date) = :month
    """)
    row = db.execute(q, {"tenant": tenant, "year": year, "month": month}).mappings().one()
    income = float(row["income"] or 0)
    expense = float(row["expense"] or 0)
    return {
        "tenant_code": tenant,
        "year": year,
        "month": month,
        "income": income,
        "expense": expense,
        "balance": income - expense,
    }
