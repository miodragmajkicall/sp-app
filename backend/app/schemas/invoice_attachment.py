from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


BaseConfig = ConfigDict(from_attributes=True, populate_by_name=True)


class InvoiceAttachmentRead(BaseModel):
    """
    Read model za attachment ulazne/izlazne fakture.

    Koristi se u svim odgovorima vezanim za:
    - upload,
    - listanje,
    - linkovanje na fakturu / ulaznu fakturu,
    - update statusa.
    """

    model_config = BaseConfig

    id: int = Field(..., description="ID attachment-a (BIGINT).")
    tenant_code: str = Field(
        ...,
        description="Šifra tenanta kojem attachment pripada.",
    )

    # Linkovi na fakture (opciono)
    invoice_id: Optional[int] = Field(
        None,
        description="ID izlazne fakture (ako je attachment povezan sa fakturom).",
    )
    input_invoice_id: Optional[int] = Field(
        None,
        description="ID ulazne fakture (računa dobavljača) ako je attachment povezan.",
    )

    filename: str = Field(
        ...,
        description="Originalno ime fajla (npr. 'ulazna-faktura-001.pdf').",
    )
    content_type: str = Field(
        ...,
        description="MIME tip fajla (npr. 'application/pdf', 'image/jpeg').",
    )
    size_bytes: int = Field(
        ...,
        description="Veličina fajla u bajtovima.",
    )

    storage_path: Optional[str] = Field(
        None,
        description=(
            "Relativna putanja do fajla u storage-u (npr. 't-demo/123_invoice.pdf'). "
            "Primarno za internu upotrebu."
        ),
    )

    status: str = Field(
        ...,
        description=(
            "Status obrade attachment-a, npr. 'uploaded', 'ocr_pending', "
            "'ocr_done', 'linked_to_invoice', 'matched_to_invoice', 'error'."
        ),
    )

    created_at: datetime = Field(
        ...,
        description="Datum i vrijeme kada je attachment uploadovan (ISO format).",
    )
