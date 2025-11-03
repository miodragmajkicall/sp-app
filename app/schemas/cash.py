from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CashEntryBase(BaseModel):
    tenant_code: Optional[str] = None
    entry_date: date
    kind: str
    amount: Decimal
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CashEntryCreate(CashEntryBase):
    pass


class CashEntryUpdate(BaseModel):
    entry_date: Optional[date] = None
    kind: Optional[str] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None


class CashEntryRead(CashEntryBase):
    id: str
    created_at: datetime
