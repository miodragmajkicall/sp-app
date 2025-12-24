# /home/miso/dev/sp-app/sp-app/backend/app/schemas/promet.py

from decimal import Decimal
from datetime import date as DateType
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class PrometRow(BaseModel):
    """
    Jedan red u Knjizi prometa (KP-1042).

    Za prvu verziju koristimo podatke iz keš knjige (CashEntry):

    - datum prometa
    - broj dokumenta (ako postoji, npr. broj fakture; u suprotnom ID zapisa)
    - naziv partnera (kupac / dobavljač) ili opis transakcije
    - iznos (pozitivan za prihode, negativan za rashode)
    - napomena (opcionalno)
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # VAŽNO: polje se zove "date", ali tip je DateType,
    # da ne bismo imali sudar imena polja i tipa.
    date: DateType = Field(
        ...,
        description="Datum prometa (datum kada je izvršen bezgotovinski promet).",
    )
    document_number: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Broj dokumenta (npr. broj izlazne fakture ili interni broj naloga).",
    )
    partner_name: str = Field(
        ...,
        min_length=1,
        description="Naziv kupca ili dobavljača (kupac/dobavljač) ili opis prometa.",
    )
    amount: Decimal = Field(
        ...,
        description=(
            "Iznos prometa u valuti tenanta (tipično BAM). "
            "Pozitivan za prihode, negativan za rashode."
        ),
    )
    note: Optional[str] = Field(
        default=None,
        description="Napomena uz stavku (opcionalno).",
    )


class PrometListResponse(BaseModel):
    """
    Response model za UI endpoint Knjige prometa.

    Tipična upotreba:
    - `total` – ukupan broj stavki koje zadovoljavaju filtere,
    - `items` – jedna stranica podataka za prikaz u tabeli.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total: int = Field(
        ...,
        ge=0,
        description="Ukupan broj stavki u Knjizi prometa koje zadovoljavaju filtere.",
    )
    items: list[PrometRow] = Field(
        ...,
        description="Lista stavki Knjige prometa.",
    )
