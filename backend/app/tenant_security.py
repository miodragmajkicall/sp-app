from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tenant

MISSING_TENANT_HEADER_MESSAGE = "Missing X-Tenant-Code header"


def require_tenant_code(x_tenant_code: Optional[str]) -> str:
    """
    Osnovna provjera da je X-Tenant-Code header postavljen.

    - Ako header nedostaje ili je prazan → HTTP 400 sa porukom
      "Missing X-Tenant-Code header".
    - Inače vraća prosleđeni kod (string).

    Ovo je centralno mjesto za provjeru, kako bi se ponašanje
    u svim modulima (cash, invoices, tax, ...) držalo konzistentnim.
    """
    if not x_tenant_code:
        raise HTTPException(status_code=400, detail=MISSING_TENANT_HEADER_MESSAGE)
    return x_tenant_code


def ensure_tenant_exists(db: Session, code: str) -> Tenant:
    """
    Pobrini se da u bazi postoji red u tabeli `tenants` sa zadatim `code`.

    - Ako tenant već postoji → vraća postojećeg.
    - Ako ne postoji → kreira se minimalni tenant sa:
        * id   = code (odrezan na max 32 karaktera)
        * code = prosleđeni kod
        * name = "Tenant {code}"

    Ovaj helper se koristi u modulima koji prvi put kreiraju podatke
    za tenanta (npr. invoices, cash), tako da backend može da radi
    "self-service" demo/test scenarije bez ručnog unosa tenant-a.
    """
    stmt = select(Tenant).where(Tenant.code == code)
    existing = db.execute(stmt).scalars().first()
    if existing:
        return existing

    tenant = Tenant(
        id=code[:32],
        code=code,
        name=f"Tenant {code}",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
