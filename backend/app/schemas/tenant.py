from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class TenantCreate(BaseModel):
    """
    Ulazni model za kreiranje novog tenanta.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "code": "t-demo",
                "name": "Demo Tenant",
            }
        },
    )

    code: str = Field(
        min_length=1,
        max_length=64,
        description="Jedinstveni kod tenanta (npr. 't-demo').",
    )
    name: str = Field(
        min_length=1,
        description="Prikazno ime tenanta (npr. naziv firme ili klijenta).",
    )


class TenantRead(BaseModel):
    """
    Model koji se vraća prema klijentu kada čitamo podatke o tenantima.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "9f5e2a4b7c3d4e1f8a2b9c6d1e3f7a5b",
                "code": "t-demo",
                "name": "Demo Tenant",
            }
        },
    )

    id: str = Field(
        ...,
        description="Primarni ključ tenanta (interni identifikator, string/UUID).",
    )
    code: str = Field(
        ...,
        description="Jedinstveni kod tenanta.",
    )
    name: str = Field(
        ...,
        description="Ime tenanta (npr. naziv firme).",
    )


class TenantUpdate(BaseModel):
    """
    Model za djelimično ažuriranje tenanta.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Novi naziv Tenanta",
            }
        },
    )

    name: str | None = Field(
        default=None,
        description="Novo ime tenanta (ako se ažurira).",
    )
