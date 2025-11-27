from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import Invoice, InvoiceItem, Tenant
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.tenant_security import require_tenant_code, ensure_tenant_exists

router = APIRouter(
    tags=["invoices"],
)


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Osigurava da je X-Tenant-Code header postavljen.
    Ako nedostaje, vraća HTTP 400.

    Implementacija delegira na shared helper iz `app.tenant_security`
    da bi svi moduli imali identično ponašanje.
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Pobrini se da u bazi postoji red u tabeli tenants sa zadatim `code`.

    Kroz shared helper `ensure_tenant_exists` dobijamo jedno centralno mjesto
    za kreiranje minimalnog tenanta kada radimo demo/test scenarije.
    """
    ensure_tenant_exists(db, code)


# ======================================================
#  CREATE
# ======================================================
@router.post(
    "/invoices",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj novu fakturu",
    description=(
        "Kreira **novu fakturu sa stavkama** za konkretnog tenanta.\n\n"
        "Back-end računa sve iznose (osnovica, PDV, total) na osnovu proslijeđenih "
        "stavki – klijent šalje samo opis, količinu, cijenu i stopu PDV-a.\n\n"
        "Ključne napomene:\n"
        "- broj fakture (`invoice_number`) mora biti jedinstven **unutar jednog tenanta**;\n"
        "- lista stavki (`items`) ne smije biti prazna;\n"
        "- tenant se određuje preko `X-Tenant-Code` header-a.\n\n"
        "Ovo je glavna ruta koju će mobilni/web UI koristiti za izdavanje faktura."
    ),
    responses={
        201: {
            "description": "Faktura je uspješno kreirana.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "tenant_code": "t-demo",
                        "invoice_number": "2025-001",
                        "issue_date": "2025-11-21",
                        "due_date": "2025-12-21",
                        "buyer_name": "Frizer Salon Milica",
                        "buyer_address": "Kralja Petra I 12, Banja Luka",
                        "total_base": "25.00",
                        "total_vat": "4.25",
                        "total_amount": "29.25",
                        "items": [
                            {
                                "id": 10,
                                "description": "Muško šišanje",
                                "quantity": "1",
                                "unit_price": "10.00",
                                "vat_rate": "0.17",
                                "base_amount": "10.00",
                                "vat_amount": "1.70",
                                "total_amount": "11.70",
                            },
                            {
                                "id": 11,
                                "description": "Pranje + feniranje",
                                "quantity": "1",
                                "unit_price": "15.00",
                                "vat_rate": "0.17",
                                "base_amount": "15.00",
                                "vat_amount": "2.55",
                                "total_amount": "17.55",
                            },
                        ],
                    }
                }
            },
        },
        400: {
            "description": (
                "Poslovna greška pri kreiranju fakture.\n\n"
                "Tipični scenariji:\n"
                "- nedostaje `X-Tenant-Code` header;\n"
                "- lista stavki (`items`) je prazna."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "missing_tenant": {
                            "summary": "Nedostaje X-Tenant-Code",
                            "value": {"detail": "Missing X-Tenant-Code header"},
                        },
                        "no_items": {
                            "summary": "Prazna lista stavki",
                            "value": {
                                "detail": "Invoice must contain at least one item"
                            },
                        },
                    }
                }
            },
        },
        409: {
            "description": (
                "Pokušaj kreiranja fakture sa brojem koji već postoji za datog tenanta."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invoice number already exists for this tenant"
                    }
                }
            },
        },
    },
)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg se kreira faktura.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
) -> Invoice:
    """
    Kreira novu fakturu sa jednom ili više stavki za zadatog tenanta.

    - Broj fakture (`invoice_number`) mora biti jedinstven po tenant-u.
    - Iznosi (osnovica, PDV, total) računaju se na serveru na osnovu stavki.
    """
    tenant = _require_tenant(x_tenant_code)

    # Osiguramo da tenant postoji (radi FK tenants.code)
    _ensure_tenant_exists(db, tenant)

    data = payload.model_dump()
    items_data = data.pop("items", [])

    if not items_data:
        raise HTTPException(
            status_code=400,
            detail="Invoice must contain at least one item",
        )

    total_base = Decimal("0.00")
    total_vat = Decimal("0.00")
    total_amount = Decimal("0.00")

    item_models: List[InvoiceItem] = []

    for item in items_data:
        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        vat_rate = Decimal(str(item["vat_rate"]))

        base_amount = qty * unit_price
        vat_amount = base_amount * vat_rate
        line_total = base_amount + vat_amount

        total_base += base_amount
        total_vat += vat_amount
        total_amount += line_total

        item_models.append(
            InvoiceItem(
                description=item["description"],
                quantity=qty,
                unit_price=unit_price,
                vat_rate=vat_rate,
                base_amount=base_amount,
                vat_amount=vat_amount,
                total_amount=line_total,
            )
        )

    invoice = Invoice(
        tenant_code=tenant,
        invoice_number=data["invoice_number"],
        issue_date=data["issue_date"],
        due_date=data.get("due_date"),
        buyer_name=data["buyer_name"],
        buyer_address=data.get("buyer_address"),
        total_base=total_base,
        total_vat=total_vat,
        total_amount=total_amount,
        items=item_models,
    )

    db.add(invoice)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Jedinstvenost invoice_number po tenant-u
        raise HTTPException(
            status_code=409,
            detail="Invoice number already exists for this tenant",
        )

    db.refresh(invoice)
    return invoice


@router.post(
    "/invoices/",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_invoice_slash(
    payload: InvoiceCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> Invoice:
    """
    Alias ruta za POST /invoices/ (sa kosom crtom na kraju),
    radi izbjegavanja 307 redirect-a u testovima/klijentu.
    """
    return create_invoice(payload=payload, db=db, x_tenant_code=x_tenant_code)


# ======================================================
#  LIST
# ======================================================
@router.get(
    "/invoices",
    response_model=List[InvoiceRead],
    summary="Lista faktura za tenanta",
    description=(
        "Vraća listu faktura za zadatog tenenta uz opcione filtere i paginaciju.\n\n"
        "Filteri:\n"
        "- `date_from` / `date_to` – opseg po `issue_date` (uključivo);\n"
        "- `buyer_name` – prefiks naziva kupca (npr. 'Buyer' → 'Buyer A', 'Buyer B');\n"
        "- `limit` i `offset` – jednostavna paginacija.\n\n"
        "Sortiranje: najnovije fakture su prve "
        "(`issue_date` silazno, pa `id` silazno)."
    ),
)
def list_invoices(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta čije fakture vraćamo.",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum (issue_date) filtera (YYYY-MM-DD, uključivo).",
        examples=["2025-01-01"],
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum (issue_date) filtera (YYYY-MM-DD, uključivo).",
        examples=["2025-01-31"],
    ),
    buyer_name: Optional[str] = Query(
        None,
        description="Filtriranje po nazivu kupca (prefiks, npr. 'Buyer').",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maksimalan broj zapisa (paginacija).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za paginaciju (broj zapisa koje preskačemo).",
    ),
) -> List[Invoice]:
    """
    Vraća listu faktura za zadatog tenanta, sa opcionom datumsko-kupac
    filtracijom i paginacijom.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(Invoice.tenant_code == tenant)

    if date_from is not None:
        stmt = stmt.where(Invoice.issue_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Invoice.issue_date <= date_to)
    if buyer_name:
        # VAŽNO: test očekuje da "Buyer" pogodi "Buyer A" i "Buyer B", ali NE "Another Buyer".
        # Zato filtriramo po prefiksu, ne po "contains".
        stmt = stmt.where(Invoice.buyer_name.ilike(f"{buyer_name}%"))

    stmt = (
        stmt.order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).scalars().unique().all()
    return list(rows)


@router.get(
    "/invoices/",
    response_model=List[InvoiceRead],
    include_in_schema=False,
)
def list_invoices_slash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    buyer_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[Invoice]:
    """
    Alias ruta za GET /invoices/ (sa kosom crtom na kraju).
    """
    return list_invoices(
        db=db,
        x_tenant_code=x_tenant_code,
        date_from=date_from,
        date_to=date_to,
        buyer_name=buyer_name,
        limit=limit,
        offset=offset,
    )


# ======================================================
#  GET BY ID
# ======================================================
@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="Dohvati jednu fakturu po ID-u",
    description=(
        "Dohvata jednu fakturu (sa svim stavkama) po njenom ID-u.\n\n"
        "Korisno za ekran detalja fakture u UI-ju. "
        "Ako faktura ne postoji ili ne pripada datom tenant-u, vraća se 404."
    ),
    responses={
        404: {
            "description": "Faktura nije pronađena za zadati ID/tenant kombinaciju.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invoice not found"}
                }
            },
        }
    },
)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem faktura mora pripadati.",
    ),
) -> Invoice:
    """
    Vraća jednu fakturu (sa stavkama) po ID-u.

    Ako faktura ne postoji ili ne pripada zadatom tenant-u, vraća se 404.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return obj


# ======================================================
#  DELETE
# ======================================================
@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Obriši fakturu",
    response_class=Response,
    description=(
        "Briše jednu fakturu i sve njene stavke.\n\n"
        "Ako faktura ne postoji ili ne pripada zadatom tenant-u, vraća se 404.\n\n"
        "Tipičan use-case: dugme *'Obriši fakturu'* u UI-ju."
    ),
    responses={
        204: {
            "description": "Faktura je uspješno obrisana. Tijelo odgovora je prazno."
        },
        404: {
            "description": "Faktura nije pronađena za zadati ID/tenant kombinaciju.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invoice not found"}
                }
            },
        },
    },
)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem faktura mora pripadati.",
    ),
) -> Response:
    """
    Briše jednu fakturu i sve njene stavke.

    Ako faktura ne postoji ili ne pripada zadatom tenant-u, vraća se 404.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Invoice not found")

    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
