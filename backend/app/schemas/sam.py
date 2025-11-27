from __future__ import annotations

from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

# Osnovna konfiguracija za sve SAM sheme:
# - from_attributes: dozvoljava mapiranje direktno iz SQLAlchemy objekata
# - populate_by_name: olakšava (de)serializaciju po nazivu polja
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class SamMonthlyItemRead(BaseModel):
    """
    Jedan mjesečni zapis obaveza prema državi za tenanta.

    Podaci se vuku iz tabele `tax_monthly_results` (DUMMY model obračuna).
    """

    model_config = BaseConfig

    year: int = Field(..., description="Godina na koju se zapis odnosi (YYYY).")
    month: int = Field(..., ge=1, le=12, description="Mjesec (1-12).")
    is_final: bool = Field(
        ...,
        description="Da li je periode već finalizovan u poreskom modulu.",
    )
    total_due: Decimal = Field(
        ...,
        description=(
            "Ukupna obaveza prema državi za dati mjesec "
            "(porez na dohodak + doprinosi), prema DUMMY modelu."
        ),
    )


class SamOverviewRead(BaseModel):
    """
    Godišnji SAM pregled obaveza za jednog tenanta (SP).

    Tipičan use-case u UI-ju:
    - ekran 'SAM pregled' gdje SP vidi:
      - po mjesecima: iznos za uplatu i da li je mjesec zaključan,
      - zbirnu godišnju obavezu koju treba da uplati državi.
    """

    model_config = BaseConfig

    tenant_code: str = Field(
        ...,
        description="Šifra tenanta (SP) na kojeg se pregled odnosi.",
    )
    year: int = Field(
        ...,
        description="Godina za koju se prikazuje SAM pregled.",
    )
    monthly: List[SamMonthlyItemRead] = Field(
        ...,
        description=(
            "Lista mjesečnih obaveza, uparena sa podacima iz `tax_monthly_results`.\n"
            "Ako za neki mjesec nema podataka, on jednostavno neće biti u listi."
        ),
    )
    yearly_total_due: Decimal = Field(
        ...,
        description=(
            "Ukupna godišnja obaveza prema državi za datu godinu.\n"
            "- Ako postoji godišnji zapis u `tax_yearly_results`, koristi se njegov `total_due`.\n"
            "- Ako godišnji zapis ne postoji, koristi se zbir `total_due` svih finalizovanih mjeseci."
        ),
    )
    currency: str = Field(
        "BAM",
        description="Valuta u kojoj su izražene obaveze (default: BAM).",
    )
