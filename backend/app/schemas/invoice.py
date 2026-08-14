from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


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
    discount_percent: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        lt=100,
        decimal_places=2,
        description="Discount percentage per item (0 <= discount < 100).",
    )
    vat_rate: Decimal = Field(
        ...,
        ge=0,
        description="Stopa PDV-a za stavku, npr. 0.17 (17%).",
    )


class InvoiceItemCreate(InvoiceItemBase):
    """Model za kreiranje stavki fakture."""

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "description": "Muško šišanje",
                "quantity": "1",
                "unit_price": "10.00",
                "discount_percent": "0.00",
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
        max_length=128,
        description="Naziv kupca/klijenta.",
    )
    buyer_address: Optional[str] = Field(
        None,
        max_length=256,
        description="Adresa kupca (opcionalno).",
    )
    buyer_type: Literal["BUSINESS", "INDIVIDUAL", "UNSPECIFIED"] = Field(
        "UNSPECIFIED",
        description="Tip kupca.",
    )
    buyer_tax_id: Optional[str] = Field(
        None,
        max_length=64,
        description="JIB/PIB poslovnog kupca (opcionalno).",
    )
    note: Optional[str] = Field(
        None,
        description="Napomena koja će se prikazati na fakturi (opcionalno).",
    )

    @model_validator(mode="after")
    def validate_buyer_tax_id(self):
        if self.buyer_type == "INDIVIDUAL" and self.buyer_tax_id is not None:
            raise ValueError("buyer_tax_id is not allowed for INDIVIDUAL buyer")
        return self


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
                "buyer_type": "BUSINESS",
                "buyer_tax_id": "4401234560001",
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

    @field_validator("invoice_number", "buyer_name", mode="before")
    @classmethod
    def normalize_required_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("buyer_address", "buyer_tax_id", "note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_due_date(self):
        if self.due_date is not None and self.due_date < self.issue_date:
            raise ValueError("due_date must be on or after issue_date")
        return self


class InvoiceRead(InvoiceBase):
    """Model koji se vraća prema klijentu."""

    model_config = BaseConfig

    id: int = Field(..., description="ID fakture (BIGINT).")
    tenant_code: str = Field(..., description="Tenant kod kojem faktura pripada.")

    issuer_business_name: Optional[str] = None
    issuer_address: Optional[str] = None
    issuer_tax_id: Optional[str] = None
    issuer_phone: Optional[str] = None
    issuer_email: Optional[str] = None
    issuer_bank_name: Optional[str] = None
    issuer_bank_account: Optional[str] = None
    issuer_iban: Optional[str] = None
    issuer_swift_bic: Optional[str] = None

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
