from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CashEntryBase(BaseModel):
    tenant_code: str = Field(min_length=1, max_length=64)
    entry_date: date
    kind: Literal["income", "expense"]
    amount: Decimal
    description: str | None = None


class CashEntryCreate(CashEntryBase):
    pass


class CashEntryUpdate(BaseModel):
    # partial update – sva polja opcionalna
    entry_date: date | None = None
    kind: Literal["income", "expense"] | None = None
    amount: Decimal | None = None
    description: str | None = None


class CashEntryRead(CashEntryBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CashSummary(BaseModel):
    tenant_code: str
    year: int
    month: int | None = None
    balance: Decimal


class CashList(BaseModel):
    # odgovara responsu GET /cash/entries -> {"items": [...]}
    items: list[CashEntryRead]

# --- CashEntryUpdate (PATCH schema) ---
from typing import Optional
try:
    # Pydantic v2
    from pydantic import BaseModel, ConfigDict  # type: ignore
    _P2 = True
except Exception:  # pragma: no cover
    # Pydantic v1 fallback (ako je potrebno)
    from pydantic import BaseModel  # type: ignore
    ConfigDict = dict  # type: ignore
    _P2 = False


class CashEntryUpdate(BaseModel):
    """
    Minimalna PATCH šema: dozvoljava parcijalna polja.
    - Držimo polja opcionalnim i uključujemo 'extra=allow' radi kompatibilnosti,
      ako u modelu postoji još atributa (npr. category_id, date, direction...).
    """
    # najčešća polja – ostavi slobodno, dodaćemo po potrebi
    amount: Optional[float] = None
    note: Optional[str] = None

    # Pydantic v2 konfiguracija (dozvoli nepoznata polja da ne pucamo na patchu)
    if _P2:
        model_config = ConfigDict(extra="allow")  # type: ignore
    # Pydantic v1 fallback:
    else:  # pragma: no cover
        class Config:
            extra = "allow"

