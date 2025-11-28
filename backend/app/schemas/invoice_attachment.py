from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class InvoiceAttachmentRead(BaseModel):
    """
    Read-model za jedan uploadovani attachment ulazne fakture.

    Ovo je meta-nivo: ne vraćamo binarni sadržaj fajla, već samo
    metapodatke koje UI koristi za listanje i odabir fajla za dalji OCR
    ili povezivanje sa konkretnom ulaznom fakturom.
    """

    model_config = BaseConfig

    id: int = Field(..., description="ID attachment-a (interni identifikator).")
    tenant_code: str = Field(..., description="Tenant kod kojem attachment pripada.")

    # Opcioni foreign key na ulaznu fakturu (kad je attachment već povezan).
    invoice_id: Optional[int] = Field(
        None,
        description="ID fakture kojoj je attachment pridružen (ako je već povezan).",
    )

    filename: str = Field(..., description="Originalno ime fajla.")
    content_type: str = Field(..., description="MIME tip fajla (npr. application/pdf).")
    size_bytes: int = Field(..., ge=0, description="Veličina fajla u bajtovima.")
    status: str = Field(
        ...,
        description=(
            "Status obrade attachment-a. U prvoj verziji: 'uploaded' ili "
            "'linked_to_invoice', a kasnije npr. 'ocr_pending', 'ocr_done', "
            "'matched_to_invoice', itd."
        ),
    )
    created_at: datetime = Field(
        ..., description="Datum/vrijeme uploada attachment-a (server time)."
    )
