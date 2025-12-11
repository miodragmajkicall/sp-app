# /home/miso/dev/sp-app/sp-app/backend/app/schemas/promet.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PrometRow(BaseModel):
    """
    Jedan red u Knjizi prometa (KP-1042).

    Napomena:
    - ovo je generički model za sve tenante,
      kasnije ćemo filtrirati / ograničavati na FBiH paušalce.
    """

    date: str
    document_number: str
    partner_name: str
    amount: float
    note: Optional[str] = None


class PrometListResponse(BaseModel):
    """
    Response model za UI endpoint Knjige prometa.

    Tipična upotreba:
    - `total` – ukupan broj stavki koje zadovoljavaju filtere,
    - `items` – jedna stranica podataka za prikaz u tabeli.
    """

    total: int
    items: List[PrometRow]
