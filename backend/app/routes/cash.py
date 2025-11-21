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

router = APIRouter(
    prefix="/cash",
    tags=["cash"],
)


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Interna pomoćna funkcija koja osigurava da je X-Tenant-Code header postavljen.

    Ako header nedostaje, baca HTTP 400.
    """
    if not x_tenant_code:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Code header")
    return x_tenant_code


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Pobrini se da u bazi postoji red u tabeli tenants sa zadatim `code`.

    - Ako tenant već postoji: ne radi ništa.
    - Ako ne postoji: kreira se minimalni tenant sa:
        id   = code (odrezan na 32 karaktera)
        code = prosleđeni kod
        name = "Tenant {code}"
    """
    stmt = select(Tenant).where(Tenant.code == code)
    existing = db.execute(stmt).scalars().first()
    if existing:
        return

    tenant = Tenant(
        id=code[:32],  # Tenant.id je String(32) → kratimo ako je duže
        code=code,
        name=f"Tenant {code}",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)


@router.get(
    "/summary",
    response_model=CashSummaryRead,
    summary="Suma prihoda, rashoda i neto rezultata",
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

    Ako `date_from` i `date_to` nisu zadati, koristi se kompletan raspon
    dostupnih zapisa za datog tenanta.
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


@router.get(
    "/",
    response_model=List[CashEntryRead],
    summary="Lista cash unosa za tenanta (uz opcione filtere i paginaciju)",
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

    Podrazumijevano (ako `limit` i `offset` nisu zadati) vraća *sve* zapise
    za tenanta, sortirane od najnovijeg ka najstarijem
    (po `created_at` i `id` u opadajućem redoslijedu).
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = (
        select(CashEntry)
        .where(CashEntry.tenant_code == tenant)
    )

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


@router.get(
    "/{cash_id}",
    response_model=CashEntryRead,
    summary="Dohvati pojedinačni cash unos po ID-u",
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

    Ako zapis ne postoji ili ne pripada zadatom tenant-u,
    vraća se HTTP 404.
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


@router.post(
    "/",
    response_model=CashEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj novi cash unos",
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
    Kreira novi cash unos (prihod ili rashod) za zadatog tenanta.

    Tenant se određuje iz `X-Tenant-Code` headera i ne nalazi se u tijelu zahtjeva.

    Primjer zahtjeva:

    - Header: `X-Tenant-Code: frizer-mika`
    - Body:
      ```json
      {
        "entry_date": "2025-01-15",
        "kind": "income",
        "amount": "100.00",
        "note": "Gotovina iz kase"
      }
      ```
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


@router.patch(
    "/{cash_id}",
    response_model=CashEntryRead,
    summary="Djelimično ažuriranje postojećeg cash unosa",
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

    Šalju se samo polja koja se mijenjaju.
    Ako zapis ne postoji ili ne pripada tenant-u, vraća se HTTP 404.
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


@router.delete(
    "/{cash_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Obriši postojeći cash unos",
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

    Ako zapis ne postoji ili ne pripada zadatom tenant-u, vraća se HTTP 404.
    Uspješno brisanje vraća HTTP 204 bez tijela odgovora.
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
