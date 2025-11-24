cat > app/schemas/cash.py <<'PY'
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict


Kind = Literal["income", "expense"]


class CashEntryBase(BaseModel):
    entry_date: date
    kind: Kind
    amount: Decimal
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CashEntryCreate(CashEntryBase):
    pass


class CashEntryUpdate(BaseModel):
    entry_date: Optional[date] = None
    kind: Optional[Kind] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None


class CashEntryRead(CashEntryBase):
    id: int
    tenant_code: str
    created_at: datetime
PY
