from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, AliasChoices
from pydantic.config import ConfigDict


# Osnovna konfiguracija za sve sheme (Pydantic v2):
# - from_attributes: omogućava validaciju iz SQLAlchemy objekata
# - populate_by_name: dozvoljava korištenje aliasa pri (de)serializaciji
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class CashEntryCreate(BaseModel):
    model_config = BaseConfig

    entry_date: date = Field(..., description="Datum knjiženja (YYYY-MM-DD).")
    kind: Literal["income", "expense"] = Field(..., description="Vrsta unosa.")
    amount: Decimal = Field(..., gt=0, description="Iznos (> 0).")
    # Klijentu izlažemo 'note', ali u bazi je 'description'.
    description: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("note", "description"),
        serialization_alias="note",
        description="Napomena (opcionalno).",
    )


class CashEntryUpdate(BaseModel):
    model_config = BaseConfig

    entry_date: Optional[date] = Field(None, description="Ažurirani datum knjiženja.")
    kind: Optional[Literal["income", "expense"]] = Field(None, description="Ažurirana vrsta.")
    amount: Optional[Decimal] = Field(None, gt=0, description="Ažurirani iznos (> 0).")
    description: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("note", "description"),
        serialization_alias="note",
        description="Ažurirana napomena.",
    )


class CashEntryRead(BaseModel):
    model_config = BaseConfig

    # >>> VAŽNO: id je sada INT (BIGINT u bazi)
    id: int = Field(..., description="Primarni ključ (autoincrement BIGINT).")
    entry_date: date
    kind: Literal["income", "expense"]
    amount: Decimal
    # prema klijentu vraćamo 'note', interno je 'description'
    description: Optional[str] = Field(
        default=None,
        serialization_alias="note",
        description="Napomena (ako postoji).",
    )
    created_at: datetime
