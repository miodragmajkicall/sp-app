# /home/miso/dev/sp-app/sp-app/backend/app/schemas/kpr.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class KprRowItem(BaseModel):
    """
    Jedan red u Knjizi prihoda i rashoda (KPR).

    Ovaj model objedinjuje podatke iz:
    - izlaznih faktura (Invoice),
    - ulaznih faktura (InputInvoice),
    - cash unosa (CashEntry).

    Služi za tabelarni prikaz u UI-ju:
    - datum (princip blagajne → za V1 koristimo issue_date/entry_date),
    - vrsta (prihod/rashod),
    - kategorija (izlazna faktura, ulazna faktura, cash),
    - kupac/dobavljač / opis,
    - broj dokumenta (broj fakture ako postoji),
    - iznos,
    - da li je rashod poreski priznat (za V1: tretiramo sve rashode kao priznate).
    """

    model_config = BaseConfig

    # Napomena:
    # - interno koristimo naziv entry_date da ne kolidira sa tipom date iz datetime
    # - prema vani (JSON/OpenAPI) polje se i dalje zove "date"
    entry_date: date = Field(
        ...,
        alias="date",
        description="Datum evidentiranja u KPR (issue_date ili entry_date).",
        examples=["2025-01-15"],
    )
    kind: Literal["income", "expense"] = Field(
        ...,
        description="Vrsta stavke: `income` (prihod) ili `expense` (rashod).",
        examples=["income"],
    )
    category: str = Field(
        ...,
        description=(
            "Kategorija izvora:\n"
            "- 'invoice'        → izlazna faktura (prihod),\n"
            "- 'input_invoice'  → ulazna faktura (rashod),\n"
            "- 'cash'           → direktan cash unos."
        ),
        examples=["invoice"],
    )
    counterparty: Optional[str] = Field(
        None,
        description=(
            "Kupac ili dobavljač, ako postoji.\n"
            "- za izlazne fakture → buyer_name,\n"
            "- za ulazne fakture  → supplier_name,\n"
            "- za cash            → može biti None."
        ),
        examples=["Frizer salon Milica", "Elektrodistribucija Banja Luka"],
    )
    document_number: Optional[str] = Field(
        None,
        description="Broj dokumenta (npr. broj fakture), ako postoji.",
        examples=["2025-001", "INV-2025-05"],
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Kratak opis transakcije (iz opisa fakture ili napomene cash unosa)."
        ),
        examples=["Račun za struju za januar", "Gotovinska uplata u kasu"],
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Iznos stavke u BAM (apsolutna vrijednost).",
        examples=["100.00"],
    )
    currency: str = Field(
        default="BAM",
        description="Valuta u kojoj je iznos izražen (default 'BAM').",
        examples=["BAM"],
    )
    tax_deductible: bool = Field(
        ...,
        description=(
            "Da li je rashod poreski priznat.\n"
            "Za V1: sve stavke tipa 'expense' tretiramo kao poreski priznate."
        ),
        examples=[True],
    )
    source: str = Field(
        ...,
        description="Izvorni entitet: 'invoice', 'input_invoice' ili 'cash'.",
        examples=["invoice"],
    )
    source_id: int = Field(
        ...,
        description=(
            "ID izvornog zapisa (Invoice.id, InputInvoice.id ili CashEntry.id)."
        ),
        examples=[1],
    )


class KprListResponse(BaseModel):
    """
    Odgovor za UI KPR tabele (Tab 1: Evidencija).

    - `total` – ukupan broj stavki koje zadovoljavaju filtere,
    - `items` – jedna stranica/redovi za tabelarni prikaz.
    """

    model_config = BaseConfig

    total: int = Field(
        ...,
        ge=0,
        description="Ukupan broj stavki u KPR-u za zadate filtere.",
        examples=[42],
    )
    items: List[KprRowItem] = Field(
        ...,
        description="Lista KPR stavki (jedna stranica za tabelu).",
    )
