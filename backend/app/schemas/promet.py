# /home/miso/dev/sp-app/sp-app/backend/app/schemas/promet.py

from decimal import Decimal
from datetime import date as DateType
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class PrometRow(BaseModel):
    """
    UI projekcija jednog canonical događaja Knjige prometa.

    Ovo nije univerzalni KP-1042 model. Konkretna zakonska projekcija
    zavisi od tenant Promet moda.

    - datum događaja
    - stvarni broj izvornog dokumenta kada postoji
    - partner ili opis događaja kada postoji
    - iznos prihoda/prometa
    - napomena (opcionalno)
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    date: DateType = Field(
        ...,
        description="Datum canonical događaja Knjige prometa.",
    )
    document_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        description=(
            "Stvarni broj izvornog dokumenta kada postoji; "
            "ne generiše se sintetički broj."
        ),
    )
    partner_name: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Naziv partnera ili eksplicitni opis događaja kada postoji.",
    )
    amount: Decimal = Field(
        ...,
        description="Iznos canonical događaja u valuti tenanta (tipično BAM).",
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
