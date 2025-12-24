from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)

# ============================================================
# INVOICE ITEMS (stavke fakture)
# ============================================================


class InvoiceItemBase(BaseModel):
    """Osnovna polja za stavke fakture."""

    model_config = BaseConfig

    description: str = Field(
        ...,
        min_length=1,
        description="Opis stavke (npr. 'Muško šišanje', 'Proizvod X').",
    )
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Količina (> 0).",
    )
    unit_price: Decimal = Field(
        ...,
        ge=0,
        description="Jedinična cijena (>= 0).",
    )
    vat_rate: Decimal = Field(
        ...,
        ge=0,
        description="Stopa PDV-a za stavku, npr. 0.17 (17%).",
    )


class InvoiceItemCreate(InvoiceItemBase):
    """Model za kreiranje stavki fakture."""

    # polja za računanje – ne šalje ih klijent!
    base_amount: Optional[Decimal] = Field(None)
    vat_amount: Optional[Decimal] = Field(None)
    total_amount: Optional[Decimal] = Field(None)

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "description": "Muško šišanje",
                "quantity": "1",
                "unit_price": "10.00",
                "vat_rate": "0.17",
            }
        },
    )


class InvoiceItemRead(InvoiceItemBase):
    """Model koji se vraća prema klijentu."""

    model_config = BaseConfig

    id: int = Field(..., description="ID stavke (BIGINT).")
    base_amount: Decimal = Field(..., description="Osnovica bez PDV-a.")
    vat_amount: Decimal = Field(..., description="Iznos PDV-a.")
    total_amount: Decimal = Field(..., description="Ukupan iznos sa PDV-om.")


# ============================================================
# INVOICE (faktura)
# ============================================================


class InvoiceBase(BaseModel):
    """Osnovna polja fakture."""

    model_config = BaseConfig

    invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Broj fakture (jedinstven po tenant-u).",
    )
    issue_date: date = Field(
        ...,
        description="Datum izdavanja (YYYY-MM-DD).",
    )
    due_date: Optional[date] = Field(
        None,
        description="Rok dospijeća (opcionalno).",
    )
    buyer_name: str = Field(
        ...,
        min_length=1,
        description="Naziv kupca/klijenta.",
    )
    buyer_address: Optional[str] = Field(
        None,
        description="Adresa kupca (opcionalno).",
    )
    note: Optional[str] = Field(
        None,
        description="Napomena koja će se prikazati na fakturi (opcionalno).",
    )


class InvoiceCreate(InvoiceBase):
    """Model za kreiranje nove fakture."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "invoice_number": "2025-001",
                "issue_date": "2025-11-21",
                "due_date": "2025-12-21",
                "buyer_name": "Frizer Salon Milica",
                "buyer_address": "Kralja Petra I 12, Banja Luka",
                "note": "Napomena na fakturi (opciono).",
                "items": [
                    {
                        "description": "Muško šišanje",
                        "quantity": "1",
                        "unit_price": "10.00",
                        "vat_rate": "0.17",
                    },
                    {
                        "description": "Pranje + feniranje",
                        "quantity": "1",
                        "unit_price": "15.00",
                        "vat_rate": "0.17",
                    },
                ],
            }
        },
    )

    items: List[InvoiceItemCreate] = Field(
        ...,
        description="Lista stavki fakture.",
        min_length=1,
    )


class InvoiceRead(InvoiceBase):
    """Model koji se vraća prema klijentu."""

    model_config = BaseConfig

    id: int = Field(..., description="ID fakture (BIGINT).")
    tenant_code: str = Field(..., description="Tenant kod kojem faktura pripada.")

    total_base: Decimal = Field(..., description="Ukupna osnovica.")
    total_vat: Decimal = Field(..., description="Ukupan PDV.")
    total_amount: Decimal = Field(..., description="Ukupan iznos sa PDV-om.")

    is_paid: bool = Field(
        ...,
        description="Status plaćanja fakture (False = neplaćena, True = plaćena).",
    )

    items: List[InvoiceItemRead] = Field(
        ...,
        description="Stavke fakture.",
    )


# ============================================================
#  UI LISTING – REDOVI ZA TABELU
# ============================================================


class InvoiceRowItem(BaseModel):
    """
    Pojedinačan red za UI tabelu faktura.
    """

    model_config = BaseConfig

    id: int = Field(..., description="ID fakture (BIGINT).")
    invoice_number: str = Field(..., description="Broj fakture.")
    issue_date: date = Field(..., description="Datum izdavanja.")
    due_date: Optional[date] = Field(None, description="Rok dospijeća.")
    buyer_name: str = Field(..., description="Naziv kupca.")
    buyer_address: Optional[str] = Field(None, description="Adresa kupca.")

    total_base: Decimal = Field(..., description="Ukupna osnovica.")
    total_vat: Decimal = Field(..., description="Ukupan PDV.")
    total_amount: Decimal = Field(..., description="Ukupan iznos sa PDV-om.")

    is_paid: bool = Field(
        ...,
        description="Status plaćanja fakture (False = neplaćena, True = plaćena).",
    )


class InvoiceListResponse(BaseModel):
    """
    Response model za UI endpoint GET /invoices/list.
    """

    model_config = BaseConfig

    total: int = Field(
        ...,
        ge=0,
        description="Ukupan broj faktura koje zadovoljavaju zadate filtere.",
    )
    items: List[InvoiceRowItem] = Field(
        ...,
        description="Lista faktura za prikaz u UI tabeli.",
    )
