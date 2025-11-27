from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Tenant
from app.schemas.cash import (
    CashEntryCreate,
    CashEntryRead,
    CashEntryUpdate,
    CashSummaryRead,
)
from app.tenant_security import require_tenant_code, ensure_tenant_exists

router = APIRouter(
    prefix="/cash",
    tags=["cash"],
)


# ======================================================
#  TENANT HELPERS – WRAPPERI OKO SHARED LOGIKE
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Interna pomoćna funkcija koja osigurava da je `X-Tenant-Code` header postavljen.

    Ako header nedostaje → baca HTTP 400 sa porukom:
    `Missing X-Tenant-Code header`.

    Implementacija delegira na shared helper iz `app.tenant_security`
    kako bi se ponašanje uskladilo sa ostalim modulima.
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Pobrini se da u bazi postoji red u tabeli `tenants` sa zadatim `code`.

    - Ako tenant već postoji → ne radi ništa.
    - Ako ne postoji → kreira se minimalni tenant (id, code, name).

    Implementacija delegira na shared helper iz `app.tenant_security`
    da bi cash i invoices modul koristili istu logiku.
    """
    ensure_tenant_exists(db, code)


# ======================================================
#  SUMMARY (income / expense / net)
# ======================================================


@router.get(
    "/summary",
    response_model=CashSummaryRead,
    summary="Suma prihoda, rashoda i neto rezultata",
    description=(
        "Vraća zbir **prihoda**, **rashoda** i **neto rezultata** za zadatog tenanta, "
        "uz opcioni datumski opseg.\n\n"
        "Ako `date_from` i `date_to` nisu zadati, koristi se kompletan raspon "
        "dostupnih zapisa za datog tenanta.\n\n"
        "Tipični UI use-case:\n"
        "- brzi rezime na dashboard-u (ukupno uplaćeno, ukupno isplaćeno, neto),\n"
        "- filter po datumu za izvještaje (npr. za jedan mjesec ili kvartal)."
    ),
    responses={
        200: {
            "description": "Uspješno izračunat rezime za traženi period.",
            "content": {
                "application/json": {
                    "example": {
                        "income": "5000.00",
                        "expense": "3200.00",
                        "net": "1800.00",
                    }
                }
            },
        },
        400: {
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Missing X-Tenant-Code header"}
                }
            },
        },
    },
)
def get_cash_summary(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg se obračunava rezime.\n"
            "Primjer: `frizer-mika`, `tenant-001`."
        ),
    ),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum filtera (YYYY-MM-DD, uključivo).",
        examples=["2025-01-01"],
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum filtera (YYYY-MM-DD, uključivo).",
        examples=["2025-01-31"],
    ),
) -> CashSummaryRead:
    """
    Vraća zbir prihoda, rashoda i neto rezultat za zadatog tenanta
    i opcioni datumski opseg.
    """
    tenant = _require_tenant(x_tenant_code)

    income_expr = func.coalesce(
        func.sum(
            case(
                (CashEntry.kind == "income", CashEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    expense_expr = func.coalesce(
        func.sum(
            case(
                (CashEntry.kind == "expense", CashEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    stmt = select(income_expr.label("income"), expense_expr.label("expense")).where(
        CashEntry.tenant_code == tenant
    )

    if date_from is not None:
        stmt = stmt.where(CashEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CashEntry.entry_date <= date_to)

    row = db.execute(stmt).one()
    income, expense = row.income, row.expense
    net = income - expense

    return CashSummaryRead(income=income, expense=expense, net=net)


# ======================================================
#  LIST
# ======================================================


@router.get(
    "/",
    response_model=List[CashEntryRead],
    summary="Lista cash unosa za tenanta (uz opcione filtere i paginaciju)",
    description=(
        "Vraća listu cash unosa (prihodi/rashodi) za zadatog tenanta, "
        "uz opcione filtere po datumu i jednostavnu paginaciju.\n\n"
        "Podrazumijevano (ako `limit` i `offset` nisu zadati) vraća **sve** zapise "
        "za tenanta, sortirane od najnovijeg ka najstarijem:\n"
        "- prvo po `created_at` (opadajuće),\n"
        "- zatim po `id` (opadajuće).\n\n"
        "Tipični scenariji:\n"
        "- prikaz svih transakcija za određeni mjesec,\n"
        "- infinite scroll lista u mobilnoj/web aplikaciji."
    ),
    responses={
        200: {
            "description": "Lista cash unosa (može biti i prazna).",
        },
        400: {
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Missing X-Tenant-Code header"}
                }
            },
        },
    },
)
def list_cash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta čije unose vraćamo.\n"
            "Obavezno: svaki tenant ima svoj logički 'konto'."
        ),
    ),
    date_from: Optional[date] = Query(
        None,
        description=(
            "Početni datum filtera (YYYY-MM-DD, uključivo).\n"
            "Ako nije zadat, ne primjenjuje se donja granica po datumu."
        ),
        examples=["2025-01-01"],
    ),
    date_to: Optional[date] = Query(
        None,
        description=(
            "Završni datum filtera (YYYY-MM-DD, uključivo).\n"
            "Ako nije zadat, ne primjenjuje se gornja granica po datumu."
        ),
        examples=["2025-01-31"],
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=1000,
        description=(
            "Maksimalan broj zapisa koji se vraća.\n"
            "Ako nije zadato, vraćaju se svi zapisi (bez limita)."
        ),
        examples=[100],
    ),
    offset: Optional[int] = Query(
        None,
        ge=0,
        description=(
            "Broj zapisa koje treba preskočiti prije vraćanja rezultata.\n"
            "Koristi se za paginaciju zajedno sa `limit`.\n"
            "Ako nije zadato, ne primjenjuje se offset."
        ),
        examples=[0],
    ),
) -> List[CashEntry]:
    """
    Vraća listu cash unosa za datog tenanta, uz opcione datumske filtere i paginaciju.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(CashEntry).where(CashEntry.tenant_code == tenant)

    if date_from is not None:
        stmt = stmt.where(CashEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CashEntry.entry_date <= date_to)

    stmt = stmt.order_by(CashEntry.created_at.desc(), CashEntry.id.desc())

    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)

    return list(db.execute(stmt).scalars().all())


# ======================================================
#  GET BY ID
# ======================================================


@router.get(
    "/{cash_id}",
    response_model=CashEntryRead,
    summary="Dohvati pojedinačni cash unos po ID-u",
    description=(
        "Dohvata jedan cash unos za zadati `cash_id` i tenanta.\n\n"
        "Ako zapis ne postoji ili ne pripada zadatom tenant-u, vraća se 404 "
        "sa porukom `Cash entry not found`."
    ),
    responses={
        200: {
            "description": "Uspješno pronađen cash unos.",
        },
        400: {
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Missing X-Tenant-Code header"}
                }
            },
        },
        404: {
            "description": "Cash unos nije pronađen za zadati ID/tenant kombinaciju.",
            "content": {
                "application/json": {
                    "example": {"detail": "Cash entry not found"}
                }
            },
        },
    },
)
def get_cash(
    cash_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem zapis mora pripadati.",
    ),
) -> CashEntry:
    """
    Vraća jedan cash unos za zadati `cash_id` i tenanta.
    """
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id,
        CashEntry.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")
    return obj


# ======================================================
#  CREATE
# ======================================================


@router.post(
    "/",
    response_model=CashEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj novi cash unos",
    description=(
        "Kreira novi cash unos (**prihod** ili **rashod**) za zadatog tenanta.\n\n"
        "Tenant se određuje iz `X-Tenant-Code` headera i **ne nalazi se** u tijelu "
        "zahtjeva.\n\n"
        "Primjer zahtjeva:\n\n"
        "```json\n"
        "{\n"
        '  "entry_date": "2025-01-15",\n'
        '  "kind": "income",\n'
        '  "amount": "100.00",\n'
        '  "note": "Gotovina iz kase"\n'
        "}\n"
        "```\n\n"
        "Napomene:\n"
        "- `kind` je `\"income\"` ili `\"expense\"`,\n"
        "- `amount` se očekuje kao decimalna vrijednost u BAM (npr. `\"100.00\"`)."
    ),
    responses={
        201: {
            "description": "Cash unos je uspješno kreiran.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "tenant_code": "t-demo",
                        "entry_date": "2025-01-15",
                        "kind": "income",
                        "amount": "100.00",
                        "note": "Gotovina iz kase",
                        "created_at": "2025-01-15T10:30:00+00:00",
                    }
                }
            },
        },
        400: {
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Missing X-Tenant-Code header"}
                }
            },
        },
        422: {
            "description": (
                "Validation error – npr. pogrešan format datuma ili iznosa "
                "u tijelu zahtjeva."
            )
        },
    },
)
def create_cash(
    payload: CashEntryCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta za kojeg se kreira novi cash unos.",
    ),
) -> CashEntry:
    """
    Kreira novi cash unos (**prihod** ili **rashod**) za zadatog tenanta.
    """
    tenant = _require_tenant(x_tenant_code)

    # Prvo osiguramo da postoji odgovarajući tenant u tabeli tenants,
    # kako bi FK cash_entries.tenant_code → tenants.code prošao.
    _ensure_tenant_exists(db, tenant)

    data = payload.model_dump()
    data.setdefault("tenant_code", tenant)
    data.setdefault("created_at", datetime.now(timezone.utc))

    obj = CashEntry(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ======================================================
#  PATCH (partial update)
# ======================================================


@router.patch(
    "/{cash_id}",
    response_model=CashEntryRead,
    summary="Djelimično ažuriranje postojećeg cash unosa",
    description=(
        "Djelimično ažurira postojeći cash unos (PATCH).\n\n"
        "Šalju se samo polja koja se mijenjaju (partial update).\n\n"
        "Tipični primjeri:\n"
        "- promjena iznosa (`amount`),\n"
        "- promjena napomene (`note`),\n"
        "- korekcija datuma (`entry_date`).\n\n"
        "Ako zapis ne postoji ili ne pripada zadatom tenant-u, vraća se 404."
    ),
    responses={
        200: {
            "description": "Cash unos je uspješno ažuriran.",
        },
        400: {
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Missing X-Tenant-Code header"}
                }
            },
        },
        404: {
            "description": "Cash unos nije pronađen za zadati ID/tenant kombinaciju.",
            "content": {
                "application/json": {
                    "example": {"detail": "Cash entry not found"}
                }
            },
        },
        422: {
            "description": (
                "Validation error – npr. pogrešan format datuma ili iznosa "
                "u tijelu zahtjeva."
            )
        },
    },
)
def patch_cash(
    cash_id: int,
    payload: CashEntryUpdate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem zapis mora pripadati.",
    ),
) -> CashEntry:
    """
    Djelimično ažurira postojeći cash unos (PATCH).
    """
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id,
        CashEntry.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ======================================================
#  DELETE
# ======================================================


@router.delete(
    "/{cash_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Obriši postojeći cash unos",
    description=(
        "Briše postojeći cash unos za zadatog tenanta.\n\n"
        "Ako zapis ne postoji ili ne pripada zadatom tenant-u, vraća se 404 "
        "sa porukom `Cash entry not found`.\n\n"
        "Uspješno brisanje vraća HTTP 204 bez tijela odgovora."
    ),
    responses={
        204: {
            "description": "Cash unos je uspješno obrisan. Tijelo odgovora je prazno."
        },
        400: {
            "description": (
                "Greška u zahtjevu – najčešće nedostaje `X-Tenant-Code` header.\n\n"
                "Primjer poruke: `Missing X-Tenant-Code header`."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Missing X-Tenant-Code header"}
                }
            },
        },
        404: {
            "description": "Cash unos nije pronađen za zadati ID/tenant kombinaciju.",
            "content": {
                "application/json": {
                    "example": {"detail": "Cash entry not found"}
                }
            },
        },
    },
)
def delete_cash(
    cash_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem zapis mora pripadati.",
    ),
) -> Response:
    """
    Briše postojeći cash unos.
    """
    tenant = _require_tenant(x_tenant_code)
    stmt = select(CashEntry).where(
        CashEntry.id == cash_id,
        CashEntry.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cash entry not found")

    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
