# backend/app/schemas/cash.py
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, condecimal

Kind = Literal["income", "expense"]

class CashEntryCreate(BaseModel):
    tenant_code: str = Field(min_length=1, max_length=64)
    entry_date: date
    kind: Kind
    amount: condecimal(max_digits=12, decimal_places=2, gt=0)
    description: Optional[str] = None

    # samo da dobijemo lijep primjer u Swagger-u
    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "tenant_code": "acme",
            "entry_date": "2025-08-15",
            "kind": "income",
            "amount": "120.50",
            "description": "Prodaja #1001",
        }]
    })

class CashEntry(BaseModel):
    id: str
    tenant_code: str
    entry_date: date
    kind: Kind
    amount: condecimal(max_digits=12, decimal_places=2)
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
