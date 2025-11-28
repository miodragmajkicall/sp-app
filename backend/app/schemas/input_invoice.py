from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

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
    issue_date: date = Field(
        ...,
        description="Datum izdavanja ulazne fakture (YYYY-MM-DD).",
    )
    due_date: Optional[date] = Field(
        None,
        description="Rok dospijeća (opcionalno).",
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

    currency: str = Field(
        default="BAM",
        min_length=1,
        max_length=8,
        description="Valuta u kojoj je račun izražen (default 'BAM').",
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
        json_schema_extra={
            "example": {
                "supplier_name": "Elektrodistribucija Banja Luka",
                "supplier_tax_id": "1234567890000",
                "supplier_address": "Kralja Petra I Karađorđevića 15, Banja Luka",
                "invoice_number": "2025-INV-001",
                "issue_date": "2025-11-01",
                "due_date": "2025-11-15",
                "total_base": "100.00",
                "total_vat": "17.00",
                "total_amount": "117.00",
                "currency": "BAM",
                "note": "Račun za električnu energiju za oktobar.",
            }
        },
    )


# ============================================================
#  INPUT INVOICE READ
# ============================================================


class InputInvoiceRead(InputInvoiceBase):
    """
    Šema koja se vraća prema klijentu za ulaznu fakturu.
    """

    model_config = BaseConfig

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
