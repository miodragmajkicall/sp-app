# /home/miso/dev/sp-app/sp-app/app/schemas/cash.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    RootModel,
    field_validator,
    AliasChoices,
)


def _normalize_amount(v: Decimal | float | int | str) -> Decimal:
    d = Decimal(str(v))
    # novčane vrijednosti na 2 decimale
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CashEntryBase(BaseModel):
    # Prihvati i "entry_date" i "date" na ulazu; serijalizacija ostaje "entry_date"
    entry_date: date = Field(..., validation_alias=AliasChoices("entry_date", "date"))
    amount: Decimal
    # Prihvati i "description" i "note" na ulazu; serijalizacija ostaje "description"
    description: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("description", "note")
    )
    # Dozvoli bilo koji string na ulazu, normalizujemo ga u validatoru
    kind: str

    model_config = ConfigDict(
        populate_by_name=True,  # koristi imena polja pri serijalizaciji
        from_attributes=True,   # dozvoli iz ORM objekata
        extra="forbid",         # odbaci nepoznata polja
    )

    @field_validator("kind")
    @classmethod
    def _normalize_kind(cls, v: str) -> str:
        v2 = v.lower().strip()
        if v2 not in ("income", "expense"):
            raise ValueError("kind must be 'income' or 'expense'")
        return v2

    @field_validator("amount", mode="before")
    @classmethod
    def _cast_amount(cls, v):
        return _normalize_amount(v)


class CashEntryCreate(CashEntryBase):
    """
    Ulaz za POST /cash/
    - Prihvata na ulazu:
        - entry_date ili date
        - description ili note
        - kind (case-insensitive): 'income' | 'expense'
        - amount: Decimal/float/int/str (normalizuje se na 2 decimale)
    """
    pass


class CashEntryUpdate(BaseModel):
    """
    Parcijalno ažuriranje za PATCH /cash/{id}
    - Sva polja su opcionalna
    - Podržani aliasi: date->entry_date, note->description
    - kind je case-insensitive
    """
    entry_date: Optional[date] = Field(
        default=None, validation_alias=AliasChoices("entry_date", "date")
    )
    amount: Optional[Decimal] = None
    description: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("description", "note")
    )
    kind: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    @field_validator("kind")
    @classmethod
    def _normalize_kind(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v2 = v.lower().strip()
        if v2 not in ("income", "expense"):
            raise ValueError("kind must be 'income' or 'expense'")
        return v2

    @field_validator("amount", mode="before")
    @classmethod
    def _cast_amount(cls, v):
        if v is None:
            return v
        return _normalize_amount(v)


class CashEntryRead(BaseModel):
    tenant_code: str
    entry_date: date
    kind: str
    amount: Decimal
    description: Optional[str] = None
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CashEntryList(RootModel[list[CashEntryRead]]):
    pass


class CashSummaryRead(BaseModel):
    """
    Rezime po transakcijama za tenant i opcione filtere datuma.
    Svi iznosi su Decimal -> serijalizuju se kao string sa 2 decimale.
    """
    tenant_code: str
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    income_total: Decimal
    expense_total: Decimal
    net_total: Decimal
    income_count: int
    expense_count: int
