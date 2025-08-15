from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel

class CashEntryCreate(BaseModel):
    tenant_code: str
    entry_date: date
    kind: str            # 'income' ili 'expense'
    amount: Decimal
    description: str | None = None

class CashEntryRead(CashEntryCreate):
    id: str
    created_at: datetime

class CashSummary(BaseModel):
    tenant_code: str
    year: int
    month: int
    balance: Decimal
