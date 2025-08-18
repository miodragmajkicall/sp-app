from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, condecimal, constr

class CashEntryCreate(BaseModel):
    tenant_code: constr(strip_whitespace=True, min_length=1, max_length=64)
    entry_date: date
    kind: Literal["income", "expense"]
    amount: condecimal(max_digits=12, decimal_places=2, gt=Decimal("0"))
    description: Optional[str] = None

class CashEntryOut(BaseModel):
    id: str
    tenant_code: str
    entry_date: date
    kind: Literal["income", "expense"]
    amount: Decimal
    description: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
