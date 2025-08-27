from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, field_validator


class CashEntryBase(BaseModel):
    entry_date: date
    kind: str
    amount: Decimal

    @field_validator("kind")
    @classmethod
    def normalize_kind(cls, v: str) -> str:
        key = str(v).strip().lower()
        mapping = {"income": "income", "expense": "expense", "in": "income", "out": "expense"}
        if key not in mapping:
            raise ValueError("kind must be 'income' or 'expense' (or IN/OUT)")
        return mapping[key]


class CashEntryCreate(CashEntryBase):
    pass


class CashEntryRead(CashEntryBase):
    id: int
    tenant_code: str

    class Config:
        from_attributes = True
