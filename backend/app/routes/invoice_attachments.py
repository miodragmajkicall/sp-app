from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.tenant_security import require_tenant_code, ensure_tenant_exists
from app.schemas.invoice_attachment import InvoiceAttachmentRead

router = APIRouter(
    prefix="/invoice-attachments",
    tags=["invoices"],  # dio invoices domena (ulazne fakture)
)


# ======================================================
#  INTERNAL IN-MEMORY STORE (v1 bez DB)
# ======================================================


@dataclass
class _AttachmentRecord:
    id: int
    tenant_code: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    status: str
    content: bytes  # binarni sadržaj fajla (za kasniju OCR obradu)


# Jednostavan in-memory store po procesu.
# Kasnije se može zamijeniti za DB (tabela invoice_attachments).
_ATTACHMENTS: Dict[int, _AttachmentRecord] = {}
_NEXT_ID: int = 1


def _next_id() -> int:
    global _NEXT_ID
    value = _NEXT_ID
    _NEXT_ID += 1
    return value


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Shared helper – potpuno isti pattern kao u invoices.py.
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Osigurava da tenant postoji u bazi (radi FK konzistentnosti u
    ostatku sistema). Ovde ga koristimo samo da se držimo istog
    ponašanja kao invoices modul.
    """
    ensure_tenant_exists(db, code)


# ======================================================
#  UPLOAD ATTACHMENT
# ======================================================


@router.post(
    "",
    response_model=InvoiceAttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload ulazne fakture (attachment)",
    description=(
        "Uploaduje jedan fajl (najčešće PDF ili sliku) kao attachment ulazne fakture "
        "za konkretnog tenanta.\n\n"
        "Ovo je prvi korak u pipeline-u za OCR i automatski unos ulaznih računa:\n"
        "- korisnik (ili mobilna aplikacija) pošalje skeniranu/slikanu fakturu,\n"
        "- backend je sačuva kao attachment uz tenanta,\n"
        "- kasnije drugi proces/endpoint može pokrenuti OCR i kreiranje ulazne fakture."
    ),
    responses={
        201: {
            "description": "Attachment je uspješno uploadovan.",
        },
        400: {
            "description": "Nedostaje X-Tenant-Code header ili fajl nije poslat.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_tenant": {
                            "summary": "Nedostaje X-Tenant-Code",
                            "value": {"detail": "Missing X-Tenant-Code header"},
                        },
                        "missing_file": {
                            "summary": "Fajl nije poslat",
                            "value": {"detail": "File is required"},
                        },
                    }
                }
            },
        },
    },
)
def upload_invoice_attachment(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem attachment pripada (npr. 't-demo').",
    ),
    file: UploadFile = File(
        ...,
        description="Fajl ulazne fakture (PDF, slika, itd.).",
    ),
) -> InvoiceAttachmentRead:
    """
    Uploaduje jedan attachment i vraća metapodatke o njemu.

    Trenutno se attachment čuva u in-memory store-u (_ATTACHMENTS),
    a kasnije se lako može prebaciti u DB bez mijenjanja API-ja.
    """
    tenant = _require_tenant(x_tenant_code)

    # Osiguramo da tenant postoji (radi konzistentnosti sa ostatkom sistema)
    _ensure_tenant_exists(db, tenant)

    if file is None:
        raise HTTPException(status_code=400, detail="File is required")

    file_bytes = file.file.read()
    size_bytes = len(file_bytes)

    if size_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    attachment_id = _next_id()
    now = datetime.now(timezone.utc)

    record = _AttachmentRecord(
        id=attachment_id,
        tenant_code=tenant,
        filename=file.filename or "uploaded-file",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        created_at=now,
        status="uploaded",
        content=file_bytes,
    )
    _ATTACHMENTS[attachment_id] = record

    return InvoiceAttachmentRead(
        id=record.id,
        tenant_code=record.tenant_code,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        status=record.status,
        created_at=record.created_at,
    )


# ======================================================
#  LIST ATTACHMENTS ZA TENANTA
# ======================================================


@router.get(
    "",
    response_model=List[InvoiceAttachmentRead],
    summary="Lista attachment-a ulaznih faktura za tenanta",
    description=(
        "Vraća listu svih uploadovanih attachment-a ulaznih faktura "
        "za zadatog tenanta.\n\n"
        "Ovo služi kao baza za ekran 'ulazne fakture' u UI-ju, gdje korisnik "
        "može vidjeti koje je fajlove uploadovao i kojim redoslijedom će se "
        "obrađivati (OCR, parsiranje, povezivanje sa troškovima, itd.)."
    ),
)
def list_invoice_attachments(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta čije attachment-e vraćamo.",
    ),
) -> List[InvoiceAttachmentRead]:
    """
    Lista attachment-a za jednog tenanta.

    Pošto u ovoj verziji attachment-e držimo u memoriji procesa,
    ovo je jednostavan filter preko internog store-a.
    """
    tenant = _require_tenant(x_tenant_code)

    # ensure_tenant_exists ovde nije striktno neophodan (jer ne diramo DB),
    # ali ga ipak pozivamo radi konzistentnosti i budućeg prelaska na DB.
    _ensure_tenant_exists(db, tenant)

    records = [
        a for a in _ATTACHMENTS.values() if a.tenant_code == tenant
    ]

    # Sortiramo po created_at silazno (najnoviji prvi)
    records.sort(key=lambda r: r.created_at, reverse=True)

    return [
        InvoiceAttachmentRead(
            id=r.id,
            tenant_code=r.tenant_code,
            filename=r.filename,
            content_type=r.content_type,
            size_bytes=r.size_bytes,
            status=r.status,
            created_at=r.created_at,
        )
        for r in records
    ]
