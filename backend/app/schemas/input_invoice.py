# /home/miso/dev/sp-app/sp-app/backend/app/schemas/input_invoice.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional, List

from pydantic import BaseModel, Field, ConfigDict


# Osnovna Pydantic konfiguracija (isto kao u drugim šemama)
BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


# ============================================================
#  INPUT INVOICE BASE
# ============================================================


class InputInvoiceBase(BaseModel):
    """
    Osnovna polja za ulaznu fakturu (račun dobavljača).

    Primjeri:
    - račun za zakup prostora
    - račun za struju, vodu, internet
    - račun dobavljača za robu / materijal
    """

    model_config = BaseConfig

    supplier_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Naziv dobavljača (npr. 'Elektrodistribucija Banja Luka').",
    )
    supplier_tax_id: Optional[str] = Field(
        None,
        max_length=64,
        description="PIB/JIB dobavljača (opcionalno).",
    )
    supplier_address: Optional[str] = Field(
        None,
        max_length=256,
        description="Adresa dobavljača (opcionalno).",
    )

    invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Broj ulazne fakture kod dobavljača.",
    )

    # Datum dokumenta (računa)
    issue_date: date = Field(
        ...,
        description="Datum izdavanja ulazne fakture (YYYY-MM-DD).",
    )

    # Datum knjiženja – može biti jednak datumu dokumenta, ali može biti i različit
    posting_date: Optional[date] = Field(
        None,
        description=(
            "Datum knjiženja u evidenciji (YYYY-MM-DD). "
            "Ako nije eksplicitno zadat, backend ga može postaviti na datum dokumenta."
        ),
    )

    # Rok dospijeća
    due_date: Optional[date] = Field(
        None,
        description="Rok dospijeća (opcionalno).",
    )

    # Kategorija troška – gorivo, kancelarija, usluge, itd.
    expense_category: Optional[str] = Field(
        None,
        max_length=64,
        description="Kategorija troška (gorivo, kancelarija, usluge, itd.).",
    )

    # Da li se rashod priznaje za porez
    is_tax_deductible: bool = Field(
        default=True,
        description=(
            "Da li se rashod priznaje za porez (true = priznat rashod, false = nepriznat)."
        ),
    )

    total_base: Decimal = Field(
        ...,
        ge=0,
        description="Osnovica bez PDV-a (>= 0).",
    )
    total_vat: Decimal = Field(
        ...,
        ge=0,
        description="Iznos PDV-a (>= 0).",
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Ukupan iznos sa PDV-om (>= 0).",
    )

    note: Optional[str] = Field(
        None,
        description="Interna napomena uz ulaznu fakturu (opcionalno).",
    )


# ============================================================
#  INPUT INVOICE CREATE
# ============================================================


class InputInvoiceCreate(InputInvoiceBase):
    """
    Šema za kreiranje nove ulazne fakture.

    Trenutno očekujemo da klijent pošalje iznose (total_base, total_vat, total_amount),
    a kasnije možemo dodati automatski obračun.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "supplier_name": "Elektrodistribucija Banja Luka",
                "supplier_tax_id": "1234567890000",
                "supplier_address": "Kralja Petra I Karađorđevića 15, Banja Luka",
                "invoice_number": "2025-INV-001",
                "issue_date": "2025-11-01",
                "posting_date": "2025-11-01",
                "due_date": "2025-11-15",
                "expense_category": "Komunalije",
                "is_tax_deductible": True,
                "total_base": "100.00",
                "total_vat": "17.00",
                "total_amount": "117.00",
                "note": "Račun za električnu energiju za oktobar.",
            }
        },
    )


# ============================================================
#  INPUT INVOICE UPDATE
# ============================================================


class InputInvoiceUpdate(BaseModel):
    """
    Šema za djelimičnu izmjenu postojeće ulazne fakture.

    Sva polja su opciona – klijent šalje samo ono što želi promijeniti.
    Business lock na nivou modela (InputInvoice.before_update) će spriječiti
    izmjene za finalizovane mjesece.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "supplier_name": "Elektrodistribucija Banja Luka",
                "due_date": "2025-11-20",
                "expense_category": "Komunalije",
                "is_tax_deductible": True,
                "note": "Ispravka roka dospijeća i dopuna napomene.",
            }
        },
    )

    supplier_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=128,
        description="Naziv dobavljača (ako se ažurira).",
    )
    supplier_tax_id: Optional[str] = Field(
        None,
        max_length=64,
        description="PIB/JIB dobavljača (ako se ažurira).",
    )
    supplier_address: Optional[str] = Field(
        None,
        max_length=256,
        description="Adresa dobavljača (ako se ažurira).",
    )

    invoice_number: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description="Broj ulazne fakture kod dobavljača (ako se ažurira).",
    )
    issue_date: Optional[date] = Field(
        None,
        description="Novi datum izdavanja ulazne fakture (YYYY-MM-DD, opcionalno).",
    )
    posting_date: Optional[date] = Field(
        None,
        description="Novi datum knjiženja (YYYY-MM-DD, opcionalno).",
    )
    due_date: Optional[date] = Field(
        None,
        description="Novi rok dospijeća (opcionalno).",
    )

    expense_category: Optional[str] = Field(
        None,
        max_length=64,
        description="Kategorija troška (ako se ažurira).",
    )

    is_tax_deductible: Optional[bool] = Field(
        None,
        description="Da li se rashod priznaje za porez (ako se mijenja).",
    )

    total_base: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Nova osnovica bez PDV-a (>= 0, opcionalno).",
    )
    total_vat: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Novi iznos PDV-a (>= 0, opcionalno).",
    )
    total_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Novi ukupan iznos sa PDV-om (>= 0, opcionalno).",
    )

    note: Optional[str] = Field(
        None,
        description="Nova interna napomena (ako se mijenja).",
    )


# ============================================================
#  INPUT INVOICE PAYMENT
# ============================================================


class InputInvoicePaymentCreate(BaseModel):
    """
    Payload za evidentiranje punog plaćanja ulazne fakture.
    Iznos se ne prima od klijenta nego ga backend uzima sa fakture.
    """

    model_config = BaseConfig

    payment_date: date = Field(
        ...,
        description="Datum plaćanja ulazne fakture (YYYY-MM-DD).",
    )
    account: Literal["cash", "bank"] = Field(
        ...,
        description="Način plaćanja: cash = kasa, bank = banka.",
    )
    note: Optional[str] = Field(
        None,
        description="Opcionalna napomena uz plaćanje.",
    )


class InputInvoicePaymentRead(BaseModel):
    """
    Evidentirano puno plaćanje ulazne fakture.
    """

    model_config = BaseConfig

    id: int = Field(..., description="ID povezanog CashEntry zapisa.")
    payment_date: date = Field(..., description="Datum plaćanja.")
    account: Literal["cash", "bank"] = Field(..., description="Kasa ili banka.")
    amount: Decimal = Field(..., description="Plaćeni iznos.")
    note: Optional[str] = Field(None, description="Napomena uz plaćanje.")


# ============================================================
#  INPUT INVOICE READ
# ============================================================


class InputInvoiceRead(InputInvoiceBase):
    """
    Šema koja se vraća prema klijentu za ulaznu fakturu.
    """

    model_config = BaseConfig

    is_paid: bool = Field(
        ...,
        description="Status plaćanja kojim upravlja payment lifecycle.",
    )
    currency: str = Field(
        ...,
        description="Valuta ulazne fakture. Trenutno BAM.",
    )

    id: int = Field(
        ...,
        description="ID ulazne fakture (BIGINT).",
    )
    tenant_code: str = Field(
        ...,
        description="Tenant kod kojem ulazna faktura pripada.",
    )
    created_at: datetime = Field(
        ...,
        description="Vrijeme kreiranja zapisa u bazi.",
    )


# ============================================================
#  UI LISTING – REDOVI + RESPONSE MODEL
# ============================================================


class InputInvoiceRowItem(BaseModel):
    """
    Pojedinačni red za UI tabelu ulaznih faktura.

    Ovo je "tanka" projekcija podataka potrebna za listanje u tabeli:
    - osnovne informacije o dobavljaču,
    - broj i datumi fakture,
    - zbirni iznosi,
    - status plaćanja i priznat rashod,
    - valuta i vrijeme kreiranja.
    """

    model_config = BaseConfig

    id: int = Field(..., description="ID ulazne fakture (BIGINT).")
    tenant_code: str = Field(..., description="Tenant kod kojem faktura pripada.")
    supplier_name: str = Field(..., description="Naziv dobavljača.")
    invoice_number: str = Field(..., description="Broj ulazne fakture.")

    issue_date: date = Field(..., description="Datum izdavanja ulazne fakture.")
    due_date: Optional[date] = Field(
        None,
        description="Rok dospijeća (ako je poznat).",
    )
    posting_date: Optional[date] = Field(
        None,
        description="Datum knjiženja (ako je poznat).",
    )

    expense_category: Optional[str] = Field(
        None,
        description="Kategorija troška (gorivo, kancelarija, usluge, itd.).",
    )
    is_tax_deductible: bool = Field(
        ...,
        description="Da li se rashod priznaje za porez.",
    )
    is_paid: bool = Field(
        ...,
        description="Status plaćanja (true = plaćeno, false = nije plaćeno).",
    )

    total_base: Decimal = Field(..., description="Osnovica bez PDV-a.")
    total_vat: Decimal = Field(..., description="Iznos PDV-a.")
    total_amount: Decimal = Field(..., description="Ukupan iznos sa PDV-om.")
    currency: str = Field(..., description="Valuta u kojoj je faktura izražena.")
    created_at: Optional[datetime] = Field(
        None,
        description="Vrijeme kreiranja zapisa (može biti null kod starih migracija).",
    )


class InputInvoiceListResponse(BaseModel):
    """
    Response model za UI endpoint GET /input-invoices/list.

    - `total` – ukupan broj ulaznih faktura koje zadovoljavaju aktivne filtere
    - `items` – jedna "stranica" podataka za prikaz u tabeli
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "total": 2,
                "items": [
                    {
                        "id": 1,
                        "tenant_code": "t-demo",
                        "supplier_name": "Elektrodistribucija Banja Luka",
                        "invoice_number": "2025-INV-001",
                        "issue_date": "2025-11-01",
                        "due_date": "2025-11-15",
                        "posting_date": "2025-11-01",
                        "expense_category": "Komunalije",
                        "is_tax_deductible": True,
                        "is_paid": False,
                        "total_base": "100.00",
                        "total_vat": "17.00",
                        "total_amount": "117.00",
                        "currency": "BAM",
                        "created_at": "2025-11-28T10:00:00+00:00",
                    },
                    {
                        "id": 2,
                        "tenant_code": "t-demo",
                        "supplier_name": "Telekom Srpske",
                        "invoice_number": "2025-INV-002",
                        "issue_date": "2025-11-05",
                        "due_date": "2025-11-20",
                        "posting_date": "2025-11-05",
                        "expense_category": "Telekom usluge",
                        "is_tax_deductible": True,
                        "is_paid": True,
                        "total_base": "50.00",
                        "total_vat": "8.50",
                        "total_amount": "58.50",
                        "currency": "BAM",
                        "created_at": "2025-11-28T11:30:00+00:00",
                    },
                ],
            }
        },
    )

    total: int = Field(
        ...,
        ge=0,
        description="Ukupan broj ulaznih faktura koje zadovoljavaju aktive filtere.",
    )
    items: List[InputInvoiceRowItem] = Field(
        ...,
        description="Lista ulaznih faktura (jedna stranica za UI tabelu).",
    )
