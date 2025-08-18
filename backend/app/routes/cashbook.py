from datetime import date
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CashEntry
from ..schemas.cashbook import CashEntryCreate, CashEntryOut

router = APIRouter(prefix="/cash", tags=["cashbook"])

@router.get("/entries", response_model=list[CashEntryOut])
def list_entries(
    tenant_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(CashEntry).filter(CashEntry.tenant_code == tenant_code)
    if date_from:
        q = q.filter(CashEntry.entry_date >= date_from)
    if date_to:
        q = q.filter(CashEntry.entry_date <= date_to)
    return q.order_by(CashEntry.entry_date.asc(), CashEntry.created_at.asc()).all()

@router.post("/entries", response_model=CashEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(payload: CashEntryCreate, db: Session = Depends(get_db)):
    entry = CashEntry(
        id=str(uuid4()),
        tenant_code=payload.tenant_code,
        entry_date=payload.entry_date,
        kind=payload.kind,
        amount=payload.amount,
        description=payload.description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: str, db: Session = Depends(get_db)):
    deleted = db.query(CashEntry).filter(CashEntry.id == entry_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.commit()
