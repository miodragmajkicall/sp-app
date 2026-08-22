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
    Query,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import Invoice, InvoiceAttachment, InputInvoice
from app.schemas.invoice_attachment import InvoiceAttachmentRead
from app.tenant_security import require_tenant_code, ensure_tenant_exists

router = APIRouter(
    prefix="/invoice-attachments",
    tags=["invoices"],  # dio invoices domena (ulazne/izlazne fakture)
)

# ======================================================
#  CONFIG: LOKALNI FILE STORAGE
# ======================================================

# Osnovni direktorij za čuvanje fajlova attachment-a.
# Može se override-ovati preko env var: INVOICE_ATTACHMENTS_DIR
STORAGE_ROOT = Path(os.getenv("INVOICE_ATTACHMENTS_DIR", "data/invoice_attachments"))

# Maksimalna veličina jednog attachment-a: 10 MiB.
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024

# Dozvoljeni statusi obrade attachment-a.
ALLOWED_ATTACHMENT_STATUSES = {
    "uploaded",
    "linked_to_invoice",
    "ocr_pending",
    "ocr_done",
    "matched_to_invoice",
    "error",
}


def _ensure_storage_root() -> None:
    """
    Osigurava da osnovni direktorij za storage postoji.
    """
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_filename(original: str | None) -> str:
    """
    Vraća siguran display/original filename za metadata.

    Korisnički filename se nikada ne koristi kao filesystem putanja.
    """
    if not original:
        return "uploaded-file"

    normalized = original.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1].strip()
    name = "".join(
        character
        for character in name
        if ord(character) >= 32 and ord(character) != 127
    )

    if not name or name in {".", ".."}:
        return "uploaded-file"

    return name[:256]


def _detect_attachment_type(file_bytes: bytes) -> tuple[str, str]:
    """
    Detektuje stvarni tip fajla iz binarnog sadržaja.

    Ne vjerujemo MIME tipu koji pošalje klijent. Dozvoljeni su samo:
    - PDF
    - JPEG
    - PNG

    Vraća canonical MIME type i sigurnu internu ekstenziju.
    """
    if b"%PDF-" in file_bytes[:1024]:
        return "application/pdf", ".pdf"

    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"

    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Unsupported attachment type; only PDF, JPEG, and PNG are allowed",
    )


def _resolve_storage_path(storage_path: str) -> Path:
    """
    Pretvara relativni storage_path u apsolutnu putanju i garantuje
    da rezultat ostaje unutar STORAGE_ROOT.

    Štiti download/delete i od traversal vrijednosti u bazi i od
    symlink putanja koje bi nakon resolve() izlazile iz storage root-a.
    """
    storage_root = STORAGE_ROOT.resolve()
    full_path = (storage_root / storage_path).resolve()

    if not full_path.is_relative_to(storage_root):
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return full_path


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
      size_bytes, status, created_at, invoice_id, input_invoice_id).
    """
    tenant = _require_tenant(x_tenant_code)

    # Osiguramo da tenant postoji (radi konzistentnosti sa ostatkom sistema)
    _ensure_tenant_exists(db, tenant)

    if file is None:
        # Teoretski ne bi trebalo da se desi jer je 'file' obavezan u FastAPI,
        # ali ostavljamo provjeru radi robusnosti.
        raise HTTPException(status_code=400, detail="File is required")

    # Čitamo najviše dozvoljeni limit + 1 bajt, tako da prevelik upload
    # ne učitavamo nekontrolisano u memoriju.
    file_bytes = file.file.read(MAX_ATTACHMENT_SIZE_BYTES + 1)
    size_bytes = len(file_bytes)

    if size_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Attachment exceeds maximum size of 10 MiB",
        )

    content_type, storage_suffix = _detect_attachment_type(file_bytes)
    original_name = _safe_filename(file.filename)

    # Osiguramo da direktorij postoji
    _ensure_storage_root()

    # 1) Kreiramo red u DB sa privremenom storage_path vrijednošću.
    # Originalni/sigurni basename čuvamo kao metadata, ali ga ne koristimo
    # za fizičku putanju na disku.
    attachment = InvoiceAttachment(
        tenant_code=tenant,
        invoice_id=None,
        input_invoice_id=None,
        filename=original_name,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path="__TEMP__",
        status="uploaded",
    )

    db.add(attachment)
    db.flush()  # dobijamo globalno jedinstven attachment.id

    # 2) Interno storage ime ne sadrži tenant niti korisnički filename.
    relative_path = f"{attachment.id}{storage_suffix}"
    full_path = STORAGE_ROOT / relative_path

    try:
        full_path.write_bytes(file_bytes)
    except OSError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store attachment file: {exc}",
        ) from exc

    # 3) Ažuriramo storage_path i commit-ujemo
    attachment.storage_path = relative_path
    db.commit()
    db.refresh(attachment)

    # FastAPI + Pydantic će od SQLAlchemy objekta napraviti InvoiceAttachmentRead
    return attachment


# ======================================================
#  LIST ATTACHMENTS ZA TENANTA (+ opcioni filter po fakturi)
# ======================================================


@router.get(
    "",
    response_model=List[InvoiceAttachmentRead],
    summary="Lista attachment-a ulaznih faktura za tenanta",
    description=(
        "Vraća listu svih uploadovanih attachment-a ulaznih faktura "
        "za zadatog tenanta.\n\n"
        "Opcioni filteri:\n"
        "- `invoice_id` – ako je zadat, vraćaju se samo attachment-i "
        "povezani sa tom izlaznom fakturom.\n"
        "- `input_invoice_id` – ako je zadat, vraćaju se samo attachment-i "
        "povezani sa tom ulaznom fakturom.\n\n"
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
    invoice_id: Optional[int] = Query(
        None,
        description=(
            "Opcioni filter: ID izlazne fakture. Ako je zadat, vraćaju se samo "
            "attachment-i koji su povezani sa tom fakturom."
        ),
    ),
    input_invoice_id: Optional[int] = Query(
        None,
        description=(
            "Opcioni filter: ID ulazne fakture. Ako je zadat, vraćaju se samo "
            "attachment-i koji su povezani sa tom ulaznom fakturom."
        ),
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

    stmt = select(InvoiceAttachment).where(InvoiceAttachment.tenant_code == tenant)

    if invoice_id is not None:
        stmt = stmt.where(InvoiceAttachment.invoice_id == invoice_id)

    if input_invoice_id is not None:
        stmt = stmt.where(
            InvoiceAttachment.input_invoice_id == input_invoice_id
        )

    stmt = stmt.order_by(
        InvoiceAttachment.created_at.desc(),
        InvoiceAttachment.id.desc(),
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

    # Brišemo samo fajl koji je dokazano unutar STORAGE_ROOT.
    if attachment.storage_path:
        full_path = _resolve_storage_path(attachment.storage_path)
        try:
            if full_path.is_file():
                full_path.unlink()
        except OSError:
            # Fizički cleanup ne smije blokirati brisanje DB zapisa ako je
            # fajl već nestao ili filesystem odbije operaciju.
            pass

    db.delete(attachment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ======================================================
#  DOWNLOAD ATTACHMENT (FAJL)
# ======================================================


@router.get(
    "/{attachment_id}/download",
    response_class=FileResponse,
    summary="Preuzmi fajl attachment-a ulazne fakture",
    description=(
        "Vraća binarni sadržaj jednog attachment-a ulazne fakture za zadatog tenanta.\n\n"
        "Tipičan use case:\n"
        "- web UI: dugme 'Preuzmi originalnu fakturu',\n"
        "- mobilna aplikacija: prikaz skenirane/slikane fakture.\n\n"
        "Ako attachment ne postoji ili ne pripada datom tenantu, vraća se 404.\n"
        "Ako je fajl fizički nestao sa diska (npr. ručno obrisan), vraća se 404."
    ),
)
def download_invoice_attachment(
    attachment_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem attachment mora pripadati.",
    ),
) -> FileResponse:
    """
    Download/preview binarnog fajla za jedan attachment.

    - provjeravamo tenant,
    - provjeravamo da attachment postoji i pripada tom tenantu,
    - provjeravamo da fajl postoji na disku,
    - vraćamo FileResponse sa odgovarajućim Content-Type i filename.
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

    if not attachment.storage_path:
        raise HTTPException(status_code=404, detail="File not found")

    full_path = _resolve_storage_path(attachment.storage_path)
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = attachment.content_type or "application/octet-stream"
    filename = attachment.filename or "attachment.bin"

    return FileResponse(
        path=full_path,
        media_type=media_type,
        filename=filename,
    )


# ======================================================
#  LINK ATTACHMENT → INVOICE (IZLAZNA FAKTURA)
# ======================================================


@router.post(
    "/{attachment_id}/link-to-invoice",
    response_model=InvoiceAttachmentRead,
    summary="Poveži attachment sa konkretnom izlaznom fakturom",
    description=(
        "Povezuje postojeći attachment sa konkretnom **izlaznom fakturom** "
        "(`invoice_id`) za istog tenanta.\n\n"
        "Tipičan tok u UI-ju:\n"
        "1. korisnik uploaduje skeniranu/slikanu fakturu,\n"
        "2. nakon ručnog unosa izlazne fakture, poveže je sa attachment-om,\n"
        "3. ovaj endpoint koristi se da se attachment 'zakači' na tu fakturu.\n\n"
        "Ako attachment ili faktura ne postoje, ili ne pripadaju zadatom tenantu, "
        "vraća se 404."
    ),
)
def link_attachment_to_invoice(
    attachment_id: int,
    payload: dict,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem attachment i faktura moraju pripadati.",
    ),
) -> InvoiceAttachmentRead:
    """
    Povezuje attachment sa izlaznom fakturom:

    - validira tenant-a,
    - provjerava da attachment postoji za tog tenanta,
    - provjerava da faktura postoji za tog tenanta,
    - postavlja invoice_id na attachment-u i status 'linked_to_invoice',
    - vraća ažurirani attachment.
    """
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

    invoice_id = payload.get("invoice_id")
    if not isinstance(invoice_id, int):
        raise HTTPException(status_code=400, detail="invoice_id is required and must be int")

    # 1) Attachment mora postojati i pripadati tenantu
    stmt_att = select(InvoiceAttachment).where(
        InvoiceAttachment.id == attachment_id,
        InvoiceAttachment.tenant_code == tenant,
    )
    attachment = db.execute(stmt_att).scalars().first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # 2) Faktura mora postojati i pripadati istom tenantu
    stmt_inv = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    invoice = db.execute(stmt_inv).scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # 3) Linkovanje
    attachment.invoice_id = invoice.id
    attachment.status = "linked_to_invoice"

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


# ======================================================
#  LINK ATTACHMENT → INPUT INVOICE (ULAZNA FAKTURA)
# ======================================================


@router.post(
    "/{attachment_id}/link-to-input-invoice",
    response_model=InvoiceAttachmentRead,
    summary="Poveži attachment sa konkretnom ulaznom fakturom",
    description=(
        "Povezuje postojeći attachment sa konkretnom **ulaznom fakturom** "
        "(`input_invoice_id`) za istog tenanta.\n\n"
        "Tipičan tok u UI-ju:\n"
        "1. korisnik uploaduje skeniranu/slikanu ulaznu fakturu (račun dobavljača),\n"
        "2. ručno ili kroz OCR kreira se entitet ulazne fakture (`input_invoices`),\n"
        "3. ovaj endpoint povezuje attachment sa tom ulaznom fakturom.\n\n"
        "Ako attachment ili ulazna faktura ne postoje, ili ne pripadaju zadatom tenantu, "
        "vraća se 404."
    ),
)
def link_attachment_to_input_invoice(
    attachment_id: int,
    payload: dict,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem attachment i ulazna faktura moraju pripadati.",
    ),
) -> InvoiceAttachmentRead:
    """
    Povezuje attachment sa ulaznom fakturom (račun dobavljača):

    - validira tenant-a,
    - provjerava da attachment postoji za tog tenanta,
    - provjerava da ulazna faktura postoji za tog tenanta,
    - postavlja input_invoice_id na attachment-u i status 'matched_to_invoice',
    - vraća ažurirani attachment.
    """
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

    input_invoice_id = payload.get("input_invoice_id")
    if not isinstance(input_invoice_id, int):
        raise HTTPException(
            status_code=400,
            detail="input_invoice_id is required and must be int",
        )

    # 1) Attachment mora postojati i pripadati tenantu
    stmt_att = select(InvoiceAttachment).where(
        InvoiceAttachment.id == attachment_id,
        InvoiceAttachment.tenant_code == tenant,
    )
    attachment = db.execute(stmt_att).scalars().first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # 2) Ulazna faktura mora postojati i pripadati istom tenantu
    stmt_inp = select(InputInvoice).where(
        InputInvoice.id == input_invoice_id,
        InputInvoice.tenant_code == tenant,
    )
    input_invoice = db.execute(stmt_inp).scalars().first()
    if not input_invoice:
        raise HTTPException(status_code=404, detail="Input invoice not found")

    # 3) Linkovanje
    attachment.input_invoice_id = input_invoice.id
    attachment.status = "matched_to_invoice"

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


# ======================================================
#  OCR STATUS SKELETON: UPDATE STATUS
# ======================================================


@router.post(
    "/{attachment_id}/status",
    response_model=InvoiceAttachmentRead,
    summary="Ažuriraj status obrade attachment-a",
    description=(
        "Ažurira status obrade za jedan attachment ulazne fakture.\n\n"
        "Dozvoljene vrijednosti:\n"
        "- `uploaded`\n"
        "- `linked_to_invoice`\n"
        "- `ocr_pending`\n"
        "- `ocr_done`\n"
        "- `matched_to_invoice`\n"
        "- `error`\n\n"
        "Ovo je skeleton za budući OCR pipeline – npr. worker može da postavi "
        "`ocr_pending` kada krene obrada, `ocr_done` kada je analiza završena, "
        "a kasnije `matched_to_invoice` kada je attachment uparen sa ulaznom fakturom."
    ),
)
def update_attachment_status(
    attachment_id: int,
    payload: dict,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem attachment mora pripadati.",
    ),
) -> InvoiceAttachmentRead:
    """
    Mijenja status attachment-a u okviru dozvoljenih vrijednosti.

    Ne uvodimo kompleksna pravila tranzicija (state machine) u ovoj fazi,
    već samo provjeravamo:
    - da je `status` validan string,
    - da je u listi ALLOWED_ATTACHMENT_STATUSES,
    - da attachment pripada zadatom tenant-u.
    """
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

    new_status = payload.get("status")
    if not isinstance(new_status, str) or new_status not in ALLOWED_ATTACHMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status value")

    stmt = select(InvoiceAttachment).where(
        InvoiceAttachment.id == attachment_id,
        InvoiceAttachment.tenant_code == tenant,
    )
    attachment = db.execute(stmt).scalars().first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    attachment.status = new_status
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment
