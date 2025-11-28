from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
    Response,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import InvoiceAttachment
from app.schemas.invoice_attachment import InvoiceAttachmentRead
from app.tenant_security import require_tenant_code, ensure_tenant_exists

router = APIRouter(
    prefix="/invoice-attachments",
    tags=["invoices"],  # dio invoices domena (ulazne fakture)
)


# ======================================================
#  CONFIG: LOKALNI FILE STORAGE
# ======================================================

# Osnovni direktorij za čuvanje fajlova attachment-a.
# Može se override-ovati preko env var: INVOICE_ATTACHMENTS_DIR
STORAGE_ROOT = Path(os.getenv("INVOICE_ATTACHMENTS_DIR", "data/invoice_attachments"))


def _ensure_storage_root() -> None:
    """
    Osigurava da osnovni direktorij za storage postoji.
    """
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_filename(original: str | None) -> str:
    """
    Vrlo jednostavna sanitizacija imena fajla:
    - uzimamo samo basename,
    - zamjenjujemo / i \ sa _,
    - ako je ime prazno, koristimo 'uploaded-file'.
    """
    if not original:
        return "uploaded-file"
    name = os.path.basename(original)
    name = name.replace("/", "_").replace("\\", "_")
    return name or "uploaded-file"


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Shared helper – potpuno isti pattern kao u invoices.py.
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Osigurava da tenant postoji u bazi (radi FK konzistentnosti).
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
        "- backend je sačuva kao attachment uz tenanta (DB + filesystem),\n"
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
                        "empty_file": {
                            "summary": "Prazan fajl",
                            "value": {"detail": "Uploaded file is empty"},
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
    Uploaduje jedan attachment, snima binarni fajl na disk i metapodatke u DB.

    API ugovor ostaje isti kao ranije:
    - vraćamo InvoiceAttachmentRead (id, tenant_code, filename, content_type,
      size_bytes, status, created_at).
    """
    tenant = _require_tenant(x_tenant_code)

    # Osiguramo da tenant postoji (radi konzistentnosti sa ostatkom sistema)
    _ensure_tenant_exists(db, tenant)

    if file is None:
        # Teoretski ne bi trebalo da se desi jer je 'file' obavezan u FastAPI,
        # ali ostavljamo provjeru radi robusnosti.
        raise HTTPException(status_code=400, detail="File is required")

    # Pročitamo sadržaj fajla u memoriju (za sada je ovo sasvim ok)
    file_bytes = file.file.read()
    size_bytes = len(file_bytes)

    if size_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    content_type = file.content_type or "application/octet-stream"
    original_name = _safe_filename(file.filename)

    # Osiguramo da direktorij postoji
    _ensure_storage_root()

    # 1) Kreiramo red u DB sa privremenim storage_path vrijednostima
    attachment = InvoiceAttachment(
        tenant_code=tenant,
        invoice_id=None,  # još nije povezano sa konkretnom ulaznom fakturom
        filename=original_name,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path="__TEMP__",  # placeholder dok ne znamo ID
        status="uploaded",
    )

    db.add(attachment)
    db.flush()  # dobijamo attachment.id iz sekvence

    # 2) Sada znamo ID → gradimo relativnu putanju i snimamo fajl na disk
    tenant_dir = STORAGE_ROOT / tenant
    tenant_dir.mkdir(parents=True, exist_ok=True)

    relative_path = f"{tenant}/{attachment.id}_{original_name}"
    full_path = STORAGE_ROOT / relative_path

    try:
        full_path.write_bytes(file_bytes)
    except OSError as exc:
        # Ako snimanje fajla padne, rollback i prijavi grešku
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store attachment file: {exc}",
        ) from exc

    # 3) Ažuriramo storage_path i commit-ujemo
    attachment.storage_path = str(relative_path)
    db.commit()
    db.refresh(attachment)

    # FastAPI + Pydantic će od SQLAlchemy objekta napraviti InvoiceAttachmentRead
    return attachment


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
    Lista attachment-a za jednog tenanta, iz baze.

    Sortiramo po created_at silazno (najnoviji prvi), zatim po id.
    """
    tenant = _require_tenant(x_tenant_code)

    # ensure_tenant_exists ovde nije strogo neophodan za SELECT,
    # ali ga ipak pozivamo radi konzistentnosti i budućih ekstenzija.
    _ensure_tenant_exists(db, tenant)

    stmt = (
        select(InvoiceAttachment)
        .where(InvoiceAttachment.tenant_code == tenant)
        .order_by(InvoiceAttachment.created_at.desc(), InvoiceAttachment.id.desc())
    )

    records = db.execute(stmt).scalars().all()
    return list(records)


# ======================================================
#  DELETE ATTACHMENT
# ======================================================


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Obriši attachment ulazne fakture",
    description=(
        "Briše jedan attachment ulazne fakture za zadatog tenanta.\n\n"
        "Operacija radi dvije stvari:\n"
        "- briše zapis iz baze (`invoice_attachments`),\n"
        "- pokušava obrisati i fajl sa disk-a (ako postoji).\n\n"
        "Ako attachment ne postoji ili ne pripada datom tenantu, vraća se 404."
    ),
)
def delete_invoice_attachment(
    attachment_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem attachment mora pripadati.",
    ),
) -> Response:
    """
    Briše jedan attachment (DB zapis + fajl na disku) za konkretnog tenanta.
    """
    tenant = _require_tenant(x_tenant_code)

    # ensure_tenant_exists radi konzistentnosti
    _ensure_tenant_exists(db, tenant)

    stmt = select(InvoiceAttachment).where(
        InvoiceAttachment.id == attachment_id,
        InvoiceAttachment.tenant_code == tenant,
    )
    attachment = db.execute(stmt).scalars().first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Pokušamo obrisati fajl sa diska, ali ne pravimo 500 ako fajl fizički ne postoji.
    if attachment.storage_path:
        full_path = STORAGE_ROOT / attachment.storage_path
        try:
            if full_path.exists():
                full_path.unlink()
        except OSError:
            # Za ovaj nivo aplikacije nije kritično ako je fajl već nestao,
            # bitno je da se biznis entitet skloni iz sistema.
            pass

    db.delete(attachment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
