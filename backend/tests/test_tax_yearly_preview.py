from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table

from app.db import SessionLocal
from app.main import app
from tests.test_tax_preview import _ensure_tenant, _cleanup_tax_test_data

client = TestClient(app)


def _cleanup_tax_monthly_results(db, tenant_code: str, year: int) -> None:
    """
    Briše zapise iz tabele tax_monthly_results za zadatog tenanta i godinu.

    Koristi refleksiju nad tabelom kako bi ostala kompatibilna sa promjenama šeme.
    """
    bind = db.get_bind()
    metadata = MetaData()
    tax_monthly_results = Table("tax_monthly_results", metadata, autoload_with=bind)

    db.execute(
        tax_monthly_results.delete().where(
            tax_monthly_results.c.tenant_code == tenant_code,
            tax_monthly_results.c.year == year,
        )
    )
    db.commit()


def _dec2(value) -> Decimal:
    """
    Pomoćna funkcija za zaokruživanje na 2 decimale (BAM).
    """
    return Decimal(str(value)).quantize(Decimal("0.01"))


def test_tax_yearly_preview_sums_finalized_months() -> None:
    """
    Test za /tax/yearly/preview:

    - pripremi tenanta
    - direktno ubaci 2 finalizovana mjeseca u tax_monthly_results (npr. januar i februar)
    - pozove /tax/yearly/preview?year=2025
    - provjeri da yearly sabira mjesečne vrijednosti
    """
    tenant_code = "t-tax-yearly-preview"
    year = 2025

    db = SessionLocal()
    try:
        _ensure_tenant(db, tenant_code)
        db.commit()

        bind = db.get_bind()
        metadata = MetaData()
        tax_monthly_results = Table(
            "tax_monthly_results", metadata, autoload_with=bind
        )

        # mjesec 1
        db.execute(
            tax_monthly_results.insert().values(
                tenant_code=tenant_code,
                year=year,
                month=1,
                total_income=Decimal("1000.00"),
                total_expense=Decimal("200.00"),
                taxable_base=Decimal("800.00"),
                income_tax=Decimal("80.00"),
                contributions_total=Decimal("200.00"),
                total_due=Decimal("280.00"),
                currency="BAM",
                is_final=True,
            )
        )

        # mjesec 2
        db.execute(
            tax_monthly_results.insert().values(
                tenant_code=tenant_code,
                year=year,
                month=2,
                total_income=Decimal("1500.00"),
                total_expense=Decimal("300.00"),
                taxable_base=Decimal("1200.00"),
                income_tax=Decimal("120.00"),
                contributions_total=Decimal("300.00"),
                total_due=Decimal("420.00"),
                currency="BAM",
                is_final=True,
            )
        )

        db.commit()

        headers = {"X-Tenant-Code": tenant_code}
        resp = client.get(
            "/tax/yearly/preview",
            params={"year": year},
            headers=headers,
        )
        assert resp.status_code == 200

        data = resp.json()

        assert data["year"] == year
        assert data["tenant_code"] == tenant_code
        assert data["months_included"] == 2
        assert data["currency"] == "BAM"

        # očekujemo sabiranje vrijednosti po poljima
        assert _dec2(data["total_income"]) == _dec2(Decimal("2500.00"))
        assert _dec2(data["total_expense"]) == _dec2(Decimal("500.00"))
        assert _dec2(data["taxable_base"]) == _dec2(Decimal("2000.00"))
        assert _dec2(data["income_tax"]) == _dec2(Decimal("200.00"))
        assert _dec2(data["contributions_total"]) == _dec2(Decimal("500.00"))
        assert _dec2(data["total_due"]) == _dec2(Decimal("700.00"))

    finally:
        _cleanup_tax_monthly_results(db, tenant_code, year)
        _cleanup_tax_test_data(db, tenant_code)
        db.close()
