from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class InvoiceAttachmentRead(BaseModel):
    """
    Read-model za jedan uploadovani attachment ulazne fakture.

    Ovo je meta-nivo: ne vraćamo binarni sadržaj fajla, već samo
    metapodatke koje UI koristi za listanje i odabir fajla za dalji OCR.
    """

    model_config = BaseConfig

    id: int = Field(..., description="ID attachment-a (interni identifikator).")
    tenant_code: str = Field(..., description="Tenant kod kojem attachment pripada.")
    filename: str = Field(..., description="Originalno ime fajla.")
    content_type: str = Field(..., description="MIME tip fajla (npr. application/pdf).")
    size_bytes: int = Field(..., ge=0, description="Veličina fajla u bajtovima.")
    status: str = Field(
        ...,
        description=(
            "Status obrade attachment-a. U prvoj verziji uvijek 'uploaded', "
            "a kasnije npr. 'ocr_pending', 'ocr_done', 'matched_to_invoice', itd."
        ),
    )
    created_at: datetime = Field(
        ..., description="Datum/vrijeme uploada attachment-a (server time)."
    )
