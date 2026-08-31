from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional, List

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic.config import ConfigDict


# Osnovna konfiguracija za sve sheme (Pydantic v2):
# - from_attributes: omogućava validaciju iz SQLAlchemy objekata
# - populate_by_name: dozvoljava korištenje aliasa pri (de)serializaciji
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class CashEntryCreate(BaseModel):
    """
    Ulazni model za kreiranje pojedinačnog ručnog cash unosa (/cash, POST).

    Tenant se određuje preko X-Tenant-Code headera.
    Invoice payment zapisima ne upravlja generic Cash CRUD.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
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
        gt=0,
        description="Iznos unosa (pozitivan decimalni broj, npr. 100.00).",
        examples=["100.00"],
    )

    account: Literal["cash", "bank"] = Field(
        default="cash",
        description=(
            "Vrsta računa:\n"
            "- `cash` → kasa (gotovina)\n"
            "- `bank` → tekući račun"
        ),
        examples=["cash"],
    )
    recognition_class: Literal[
        "business_activity",
        "cash_only",
    ] = Field(
        default="business_activity",
        description=(
            "Klasifikacija ručnog novčanog događaja. "
            "`business_activity` je podrazumijevana radi kompatibilnosti; "
            "`cash_only` označava samo novčani tok."
        ),
    )
    tax_treatment: Optional[
        Literal["deductible", "nondeductible", "unresolved"]
    ] = Field(
        default=None,
        description="Poreski tretman ručnog poslovnog rashoda.",
    )


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
    Ulazni model za djelimično ažuriranje postojećeg ručnog cash unosa
    (/cash/{id}, PATCH).

    Sva polja su opcionalna – šalju se samo ona koja treba izmijeniti.
    Invoice linkovima ne upravlja generic Cash CRUD.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )

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

    account: Optional[Literal["cash", "bank"]] = Field(
        default=None,
        description=(
            "Ažurirana vrsta računa (ako se mijenja):\n"
            "- `cash` → kasa (gotovina)\n"
            "- `bank` → tekući račun"
        ),
        examples=["bank"],
    )
    recognition_class: Optional[
        Literal["business_activity", "cash_only"]
    ] = Field(
        default=None,
        description="Ažurirana klasifikacija ručnog novčanog događaja.",
    )
    tax_treatment: Optional[
        Literal["deductible", "nondeductible", "unresolved"]
    ] = Field(
        default=None,
        description="Ažurirani poreski tretman ručnog poslovnog rashoda.",
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

    @field_validator(
        "entry_date",
        "kind",
        "amount",
        "account",
        "recognition_class",
        mode="before",
    )
    @classmethod
    def reject_null_for_required_fields(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class CashEntryRead(BaseModel):
    """
    Izlazni model za prikaz pojedinačnog cash unosa.

    Koristi se u odgovorima za:
    - kreiranje novog unosa (/cash, POST),
    - dohvat pojedinačnog unosa (/cash/{id}, GET),
    - listanje unosa (/cash, GET) – ako ruta vraća listu ovih objekata.
    """

    model_config = BaseConfig

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

    account: Literal["cash", "bank"] = Field(
        ...,
        description="Vrsta računa: `cash` (kasa) ili `bank` (tekući račun).",
        examples=["cash"],
    )
    recognition_class: Optional[
        Literal["business_activity", "cash_only"]
    ] = Field(
        default=None,
        description=(
            "Klasifikacija ručnog novčanog događaja. "
            "Linked invoice payment zapisima vrijednost može biti null."
        ),
    )
    tax_treatment: Optional[
        Literal["deductible", "nondeductible", "unresolved"]
    ] = Field(
        default=None,
        description="Poreski tretman ručnog poslovnog rashoda.",
    )
    invoice_id: Optional[int] = Field(
        default=None,
        description="ID izlazne fakture (ako postoji veza).",
        examples=[101],
    )
    input_invoice_id: Optional[int] = Field(
        default=None,
        description="ID ulazne fakture (ako postoji veza).",
        examples=[55],
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
    Izlazni model za sumarni prikaz novčanih tokova.
    """

    model_config = BaseConfig

    income: Decimal = Field(
        ...,
        description="Ukupan priliv (`income`) za zadani period i tenant.",
        examples=["1500.00"],
    )
    expense: Decimal = Field(
        ...,
        description="Ukupan odliv (`expense`) za zadani period i tenant.",
        examples=["500.00"],
    )
    net: Decimal = Field(
        ...,
        description="Neto novčani tok: income - expense.",
        examples=["1000.00"],
    )
    cash_net: Decimal = Field(
        ...,
        description="Neto novčani tok kase za zadani period.",
        examples=["600.00"],
    )
    bank_net: Decimal = Field(
        ...,
        description="Neto novčani tok tekućeg računa za zadani period.",
        examples=["400.00"],
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Broj CashEntry zapisa uključenih u summary.",
        examples=[25],
    )


# ============================================================
#  UI LISTING – CashRowItem & CashListResponse
# ============================================================


class CashRowItem(BaseModel):
    """
    Pojedinačni red kanonske Cash/Bank liste.
    """

    model_config = BaseConfig

    id: int = Field(
        ...,
        description="Primarni ključ zapisa (BIGINT u bazi).",
        examples=[1],
    )
    entry_date: date = Field(
        ...,
        description="Datum stvarnog novčanog kretanja (YYYY-MM-DD).",
        examples=["2025-01-15"],
    )
    kind: Literal["income", "expense"] = Field(
        ...,
        description="Vrsta unosa: `income` (prihod) ili `expense` (rashod).",
        examples=["income"],
    )
    amount: Decimal = Field(
        ...,
        description="Iznos unosa (pozitivan decimalni broj).",
        examples=["100.00"],
    )
    account: Literal["cash", "bank"] = Field(
        ...,
        description="Račun: `cash` (kasa) ili `bank` (banka).",
        examples=["cash"],
    )
    recognition_class: Optional[
        Literal["business_activity", "cash_only"]
    ] = Field(
        default=None,
        description=(
            "Klasifikacija ručnog novčanog događaja. "
            "`business_activity` označava kandidata za poslovno recognition "
            "evidentiranje, a `cash_only` samo novčani tok. "
            "Linked invoice payment zapisima vrijednost može biti null."
        ),
    )
    tax_treatment: Optional[
        Literal["deductible", "nondeductible", "unresolved"]
    ] = Field(
        default=None,
        description="Poreski tretman ručnog poslovnog rashoda.",
    )


    invoice_id: Optional[int] = Field(
        default=None,
        description="ID povezane izlazne fakture, radi kompatibilnosti read contracta.",
    )
    input_invoice_id: Optional[int] = Field(
        default=None,
        description="ID povezane ulazne fakture, radi kompatibilnosti read contracta.",
    )

    source_type: Literal[
        "manual",
        "output_invoice_payment",
        "input_invoice_payment",
    ] = Field(
        ...,
        description="Poslovni izvor CashEntry zapisa.",
    )
    source_document_id: Optional[int] = Field(
        default=None,
        description="ID izvornog dokumenta ako je zapis nastao kroz payment lifecycle.",
    )
    source_document_number: Optional[str] = Field(
        default=None,
        description="Broj povezane izlazne ili ulazne fakture.",
    )
    source_party_name: Optional[str] = Field(
        default=None,
        description="Kupac ili dobavljač povezanog dokumenta.",
    )

    description: Optional[str] = Field(
        default=None,
        serialization_alias="note",
        description="Napomena (ako postoji).",
        examples=["Note 001-2025-01"],
    )
    created_at: datetime = Field(
        ...,
        description="Vrijeme kreiranja zapisa (UTC datetime).",
        examples=["2025-01-15T10:30:00Z"],
    )


class CashListResponse(BaseModel):
    """
    Kanonski paginirani response za Cash/Bank listu.
    """

    model_config = BaseConfig

    total: int = Field(
        ...,
        description="Ukupan broj zapisa koji zadovoljavaju aktivne filtere.",
        examples=[3],
    )
    limit: int = Field(
        ...,
        description="Maksimalan broj zapisa na trenutnoj stranici.",
        examples=[20],
    )
    offset: int = Field(
        ...,
        description="Broj zapisa preskočenih prije trenutne stranice.",
        examples=[0],
    )
    items: List[CashRowItem] = Field(
        ...,
        description="Lista Cash/Bank zapisa za trenutnu stranicu.",
    )
