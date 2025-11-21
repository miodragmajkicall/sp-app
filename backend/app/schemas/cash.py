from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic.config import ConfigDict


# Osnovna konfiguracija za sve sheme (Pydantic v2):
# - from_attributes: omogućava validaciju iz SQLAlchemy objekata
# - populate_by_name: dozvoljava korištenje aliasa pri (de)serializaciji
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class CashEntryCreate(BaseModel):
    """
    Ulazni model za kreiranje pojedinačnog cash unosa (/cash, POST).

    Ovaj model predstavlja jedan finansijski događaj (prihod ili rashod).
    Tenant se određuje preko X-Tenant-Code headera i zato se ne pojavljuje u tijelu zahtjeva.
    """

    model_config = BaseConfig

    entry_date: date = Field(
        ...,
        description="Datum knjiženja (YYYY-MM-DD).",
        examples=["2025-01-15"],
    )
    kind: Literal["income", "expense"] = Field(
        ...,
        description=(
            "Vrsta unosa:\n"
            "- `income`  → prihod\n"
            "- `expense` → rashod"
        ),
        examples=["income"],
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Iznos unosa (pozitivan decimalni broj, npr. 100.00).",
        examples=["100.00"],
    )
    # Klijentu izlažemo 'note', ali u bazi je 'description'.
    description: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("note", "description"),
        serialization_alias="note",
        description=(
            "Napomena uz unos (opcionalno).\n"
            "Pri slanju prema API-ju može se koristiti i polje `note` ili `description`."
        ),
        examples=["Gotovina iz kase", "Plaćanje računa za struju"],
    )


class CashEntryUpdate(BaseModel):
    """
    Ulazni model za djelimično ažuriranje postojećeg cash unosa (/cash/{id}, PATCH).

    Sva polja su opcionalna – šalju se samo ona koja treba izmijeniti.
    """

    model_config = BaseConfig

    entry_date: Optional[date] = Field(
        None,
        description="Ažurirani datum knjiženja (ako se mijenja).",
        examples=["2025-01-20"],
    )
    kind: Optional[Literal["income", "expense"]] = Field(
        None,
        description=(
            "Ažurirana vrsta unosa (ako se mijenja):\n"
            "- `income`  → prihod\n"
            "- `expense` → rashod"
        ),
        examples=["expense"],
    )
    amount: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Ažurirani iznos (ako se mijenja, mora biti > 0).",
        examples=["250.50"],
    )
    description: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("note", "description"),
        serialization_alias="note",
        description=(
            "Ažurirana napomena (ako se mijenja).\n"
            "Pri slanju prema API-ju može se koristiti i `note` ili `description`."
        ),
        examples=["Ispravka prethodnog zapisa"],
    )


class CashEntryRead(BaseModel):
    """
    Izlazni model za prikaz pojedinačnog cash unosa.

    Koristi se u odgovorima za:
    - kreiranje novog unosa (/cash, POST),
    - dohvat pojedinačnog unosa (/cash/{id}, GET),
    - listanje unosa (/cash, GET) – ako ruta vraća listu ovih objekata.
    """

    model_config = BaseConfig

    # >>> VAŽNO: id je sada INT (BIGINT u bazi)
    id: int = Field(
        ...,
        description="Primarni ključ zapisa (autoincrement BIGINT u bazi).",
        examples=[1],
    )
    entry_date: date = Field(
        ...,
        description="Datum knjiženja (YYYY-MM-DD).",
        examples=["2025-01-15"],
    )
    kind: Literal["income", "expense"] = Field(
        ...,
        description=(
            "Vrsta unosa:\n"
            "- `income`  → prihod\n"
            "- `expense` → rashod"
        ),
        examples=["income"],
    )
    amount: Decimal = Field(
        ...,
        description="Iznos unosa (pozitivan decimalni broj).",
        examples=["100.00"],
    )
    # prema klijentu vraćamo 'note', interno je 'description'
    description: Optional[str] = Field(
        default=None,
        serialization_alias="note",
        description="Napomena (ako postoji).",
        examples=["Gotovina iz kase"],
    )
    created_at: datetime = Field(
        ...,
        description="Vrijeme kreiranja zapisa (UTC datetime).",
        examples=["2025-01-15T10:30:00Z"],
    )


class CashSummaryRead(BaseModel):
    """
    Izlazni model za sumarni prikaz prihoda i rashoda.

    Tipičan odgovor za rutu npr. `/cash/summary` za zadani period i tenant.
    """

    model_config = BaseConfig

    income: Decimal = Field(
        ...,
        description="Ukupan prihod (suma svih `income` unosa) za zadani period i tenant.",
        examples=["1500.00"],
    )
    expense: Decimal = Field(
        ...,
        description="Ukupan rashod (suma svih `expense` unosa) za zadani period i tenant.",
        examples=["500.00"],
    )
    net: Decimal = Field(
        ...,
        description="Neto rezultat: income - expense za zadani period i tenant.",
        examples=["1000.00"],
    )
