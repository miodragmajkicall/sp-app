from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, select

from app.db import SessionLocal
from app.main import app
from tests.test_tax_preview import _ensure_tenant, _cleanup_tax_test_data
from tests.test_tax_yearly_preview import _cleanup_tax_monthly_results

client = TestClient(app)


def _cleanup_tax_yearly_results(db, tenant_code: str, year: int) -> None:
    """
    Briše zapise iz tabele tax_yearly_results za zadatog tenanta i godinu.
    """
    bind = db.get_bind()
    metadata = MetaData()
    tax_yearly_results = Table("tax_yearly_results", metadata, autoload_with=bind)

    db.execute(
        tax_yearly_results.delete().where(
            tax_yearly_results.c.tenant_code == tenant_code,
            tax_yearly_results.c.year == year,
        )
    )
    db.commit()


def _dec2(value) -> Decimal:
    """
    Pomoćna funkcija za zaokruživanje na 2 decimale (BAM).
    """
    return Decimal(str(value)).quantize(Decimal("0.01"))


def test_tax_yearly_finalize_persists_result_and_prevents_double_finalize() -> None:
    """
    Test za /tax/yearly/finalize:

    - pripremi tenanta
    - direktno ubaci 2 finalizovana mjeseca u tax_monthly_results
    - pozove /tax/yearly/finalize?year=2025
    - provjeri da je rezultat upisan u tax_yearly_results sa sabranim vrijednostima
    - provjeri da drugi poziv vraća 400 i da nema duplih zapisa
    """
    tenant_code = "t-tax-yearly-finalize-1"
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
        tax_yearly_results = Table(
            "tax_yearly_results", metadata, autoload_with=bind
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
        params = {"year": year}

        # 1) Prvi poziv – treba da uspije
        resp = client.post("/tax/yearly/finalize", params=params, headers=headers)
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

        # 1b) Provjera da je zapis u bazi
        row = db.execute(
            select(tax_yearly_results).where(
                tax_yearly_results.c.tenant_code == tenant_code,
                tax_yearly_results.c.year == year,
            )
        ).first()
        assert row is not None

        assert _dec2(row.total_income) == _dec2(Decimal("2500.00"))
        assert _dec2(row.total_expense) == _dec2(Decimal("500.00"))
        assert _dec2(row.taxable_base) == _dec2(Decimal("2000.00"))
        assert _dec2(row.income_tax) == _dec2(Decimal("200.00"))
        assert _dec2(row.contributions_total) == _dec2(Decimal("500.00"))
        assert _dec2(row.total_due) == _dec2(Decimal("700.00"))
        assert row.months_included == 2
        assert row.currency == "BAM"
        assert bool(row.is_final) is True

        # 2) Drugi poziv za istu godinu mora da padne sa 400
        resp_2 = client.post("/tax/yearly/finalize", params=params, headers=headers)
        assert resp_2.status_code == 400

        data_err = resp_2.json()
        assert (
            data_err.get("detail")
            == "Yearly tax result for this year is already finalized"
        )

        # U bazi i dalje treba da postoji samo jedan zapis za tu godinu
        rows = db.execute(
            select(tax_yearly_results).where(
                tax_yearly_results.c.tenant_code == tenant_code,
                tax_yearly_results.c.year == year,
            )
        ).fetchall()
        assert len(rows) == 1

    finally:
        _cleanup_tax_yearly_results(db, tenant_code, year)
        _cleanup_tax_monthly_results(db, tenant_code, year)
        _cleanup_tax_test_data(db, tenant_code)
        db.close()


def test_tax_yearly_finalize_requires_finalized_months() -> None:
    """
    Testira da /tax/yearly/finalize vraća 400 ako za zadatu godinu
    ne postoji nijedan finalizovan mjesečni rezultat.
    """
    tenant_code = "t-tax-yearly-finalize-2"
    year = 2025

    db = SessionLocal()
    try:
        _ensure_tenant(db, tenant_code)
        db.commit()

        # Osiguramo da nema zapisa u tax_monthly_results za ovu godinu
        _cleanup_tax_monthly_results(db, tenant_code, year)

        headers = {"X-Tenant-Code": tenant_code}
        params = {"year": year}

        resp = client.post("/tax/yearly/finalize", params=params, headers=headers)
        assert resp.status_code == 400

        data_err = resp.json()
        assert (
            data_err.get("detail")
            == "No finalized monthly tax results for this year; cannot finalize yearly tax result"
        )

    finally:
        _cleanup_tax_yearly_results(db, tenant_code, year)
        _cleanup_tax_monthly_results(db, tenant_code, year)
        _cleanup_tax_test_data(db, tenant_code)
        db.close()
