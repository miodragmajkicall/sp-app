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


def test_tax_monthly_history_and_status_for_year() -> None:
    """
    Integracioni test za /tax/monthly/history i /tax/monthly/status.

    Scenario:
    - pripremi tenanta
    - pozove /tax/monthly/finalize za januar i februar 2025
    - pozove /tax/monthly/history?year=2025 i provjeri:
        * da vraća 2 zapisa (mjeseci 1 i 2)
        * da su is_final=True i valuta BAM
    - pozove /tax/monthly/status?year=2025 i provjeri:
        * da ima 12 mjeseci
        * da su za mjesece 1 i 2 is_final=True, has_data=True
        * da su za ostale mjesece is_final=False, has_data=False
    """
    tenant_code = "t-tax-history-status"
    year = 2025

    db = SessionLocal()
    try:
        # 0) Kreiraj tenanta i COMMIT da bi ga vidjele i druge sesije (FK na tax_monthly_results)
        _ensure_tenant(db, tenant_code)
        db.commit()

        headers = {"X-Tenant-Code": tenant_code}

        # 1) Finalizuj januar i februar 2025 preko API-ja
        for month in (1, 2):
            resp_finalize = client.post(
                "/tax/monthly/finalize",
                params={"year": year, "month": month},
                headers=headers,
            )
            # Finalize ne bi trebalo da puca
            assert resp_finalize.status_code == 200
            data = resp_finalize.json()
            assert data["year"] == year
            assert data["month"] == month
            assert data["tenant_code"] == tenant_code
            assert data["is_final"] is True
            assert data["currency"] == "BAM"

        # 2) Provjera /tax/monthly/history
        resp_history = client.get(
            "/tax/monthly/history",
            params={"year": year},
            headers=headers,
        )
        assert resp_history.status_code == 200
        history_data = resp_history.json()

        # očekujemo zapise samo za mjesece 1 i 2
        assert isinstance(history_data, list)
        months = {item["month"] for item in history_data}
        assert months == {1, 2}

        for item in history_data:
            assert item["year"] == year
            assert item["tenant_code"] == tenant_code
            assert item["is_final"] is True
            assert item["currency"] == "BAM"
            # total_income, total_expense i ostala polja su brojevi u string formatu
            # (Decimal serializacija) – provjeravamo da se mogu parsirati na 2 decimale
            _dec2(item["total_income"])
            _dec2(item["total_expense"])
            _dec2(item["taxable_base"])
            _dec2(item["income_tax"])
            _dec2(item["contributions_total"])
            _dec2(item["total_due"])

        # 3) Provjera /tax/monthly/status
        resp_status = client.get(
            "/tax/monthly/status",
            params={"year": year},
            headers=headers,
        )
        assert resp_status.status_code == 200
        status_data = resp_status.json()

        assert status_data["year"] == year
        assert status_data["tenant_code"] == tenant_code

        items = status_data["items"]
        assert isinstance(items, list)
        assert len(items) == 12

        by_month = {item["month"]: item for item in items}

        for m in range(1, 13):
            assert m in by_month
            item = by_month[m]
            assert item["month"] == m
            if m in (1, 2):
                assert item["is_final"] is True
                assert item["has_data"] is True
            else:
                assert item["is_final"] is False
                assert item["has_data"] is False

    finally:
        # Prvo očistimo tax_monthly_results, pa ostatak test podataka
        _cleanup_tax_monthly_results(db, tenant_code, year)
        _cleanup_tax_test_data(db, tenant_code)
        db.close()
