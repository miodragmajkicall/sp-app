from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.db import get_session as _get_session_dep
from app.models import CashEntry, Invoice, TaxMonthlyResult
from app.tenant_security import ensure_tenant_exists

client = TestClient(app)


@contextmanager
def _db_session_for_test():
    """
    Helper za direktan rad sa DB unutar testova.

    Koristimo isti get_session dependency kao i API.
    """
    gen = _get_session_dep()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_dashboard_year_summary_happy_path() -> None:
    """
    Happy-path test za GET /dashboard/summary/{year}:

    - pripremimo nekoliko cash unosa, faktura i poreznih rezultata u DB za tenanta,
    - pozovemo endpoint,
    - provjerimo da su agregirane vrijednosti tačne, uključujući i SAM blok.
    """
    tenant = "dash-tenant-a"
    year = 2088

    with _db_session_for_test() as db:
        # Osiguramo da tenant postoji (kroz isti helper kao API)
        ensure_tenant_exists(db, tenant)

        # Očistimo potencijalne stare zapise za ovog tenanta/godinu
        db.query(TaxMonthlyResult).filter(
            TaxMonthlyResult.tenant_code == tenant,
            TaxMonthlyResult.year == year,
        ).delete()
        db.query(CashEntry).filter(
            CashEntry.tenant_code == tenant,
            date(year, 1, 1) <= CashEntry.entry_date,
            CashEntry.entry_date <= date(year, 12, 31),
        ).delete()
        db.query(Invoice).filter(
            Invoice.tenant_code == tenant,
            date(year, 1, 1) <= Invoice.issue_date,
            Invoice.issue_date <= date(year, 12, 31),
        ).delete()
        db.commit()

        # CASH:
        # income: 100.00 + 50.00 = 150.00
        # expense: 40.00
        db.add_all(
            [
                CashEntry(
                    tenant_code=tenant,
                    entry_date=date(year, 1, 10),
                    kind="income",
                    amount=Decimal("100.00"),
                    description="Prihod 1",
                ),
                CashEntry(
                    tenant_code=tenant,
                    entry_date=date(year, 2, 5),
                    kind="income",
                    amount=Decimal("50.00"),
                    description="Prihod 2",
                ),
                CashEntry(
                    tenant_code=tenant,
                    entry_date=date(year, 3, 1),
                    kind="expense",
                    amount=Decimal("40.00"),
                    description="Rashod 1",
                ),
            ]
        )

        # INVOICES:
        # total_amount: 200.00 + 80.00 = 280.00
        inv1 = Invoice(
            tenant_code=tenant,
            invoice_number="DASH-INV-1",
            issue_date=date(year, 1, 15),
            due_date=date(year, 2, 15),
            buyer_name="Kupac 1",
            buyer_address="Adresa 1",
            total_base=Decimal("150.00"),
            total_vat=Decimal("50.00"),
            total_amount=Decimal("200.00"),
        )
        inv2 = Invoice(
            tenant_code=tenant,
            invoice_number="DASH-INV-2",
            issue_date=date(year, 4, 10),
            due_date=None,
            buyer_name="Kupac 2",
            buyer_address=None,
            total_base=Decimal("80.00"),
            total_vat=Decimal("0.00"),
            total_amount=Decimal("80.00"),
        )
        db.add_all([inv1, inv2])

        # TAX MONTHLY RESULTS:
        # zapisi za 3 mjeseca, total_due: 50.00 + 100.00 + 150.00 = 300.00
        db.add_all(
            [
                TaxMonthlyResult(
                    tenant_code=tenant,
                    year=year,
                    month=1,
                    total_income=Decimal("100.00"),
                    total_expense=Decimal("0.00"),
                    taxable_base=Decimal("100.00"),
                    income_tax=Decimal("10.00"),
                    contributions_total=Decimal("40.00"),
                    total_due=Decimal("50.00"),
                    currency="BAM",
                    is_final=True,
                ),
                TaxMonthlyResult(
                    tenant_code=tenant,
                    year=year,
                    month=2,
                    total_income=Decimal("200.00"),
                    total_expense=Decimal("0.00"),
                    taxable_base=Decimal("200.00"),
                    income_tax=Decimal("20.00"),
                    contributions_total=Decimal("80.00"),
                    total_due=Decimal("100.00"),
                    currency="BAM",
                    is_final=True,
                ),
                # jedan nefinišalizovan mjesec (is_final=False) – trenutno ga i dalje
                # računamo u dashboardu (finalized_months + total_due),
                # endpoint i test su usklađeni sa tom logikom.
                TaxMonthlyResult(
                    tenant_code=tenant,
                    year=year,
                    month=3,
                    total_income=Decimal("300.00"),
                    total_expense=Decimal("0.00"),
                    taxable_base=Decimal("300.00"),
                    income_tax=Decimal("30.00"),
                    contributions_total=Decimal("120.00"),
                    total_due=Decimal("150.00"),
                    currency="BAM",
                    is_final=False,
                ),
            ]
        )

        db.commit()

    resp = client.get(
        f"/dashboard/summary/{year}",
        headers={"X-Tenant-Code": tenant},
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["tenant_code"] == tenant
    assert data["year"] == year

    # CASH
    cash = data["cash"]
    assert cash["year"] == year
    assert cash["income_total"] == "150.00"
    assert cash["expense_total"] == "40.00"
    assert cash["net_cashflow"] == "110.00"

    # INVOICES
    inv = data["invoices"]
    assert inv["year"] == year
    assert inv["invoices_count"] == 2
    assert inv["total_amount"] == "280.00"

    # TAX
    tax = data["tax"]
    assert tax["year"] == year
    # Brojimo SVE zapise za godinu (bez filtriranja po is_final),
    # jer DashboardYearSummary trenutno ne razlikuje finalizovane/nefinalizovane.
    assert tax["finalized_months"] == 3
    assert tax["total_due"] == "300.00"  # 50 + 100 + 150

    # SAM
    sam = data["sam"]
    assert sam["year"] == year
    # SAM yearly_total_due trenutno direktno reflektuje tax.total_due
    assert sam["yearly_total_due"] == "300.00"
    assert sam["has_any_finalized"] is True


def test_dashboard_requires_tenant_header() -> None:
    """
    Bez X-Tenant-Code header-a dashboard treba da vrati 400.
    """
    resp = client.get("/dashboard/summary/2088")
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("detail") == "Missing X-Tenant-Code header"
