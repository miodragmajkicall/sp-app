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


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def test_dashboard_monthly_summary_happy_path() -> None:
    """
    Happy-path test za GET /dashboard/monthly/{year}/{month}:

    - pripremimo nekoliko cash unosa, faktura i jedan poreski rezultat u DB za tenanta,
    - pozovemo endpoint,
    - provjerimo da su agregirane vrijednosti tačne.
    """
    tenant = "dash-tenant-monthly"
    year = 2088
    month = 3

    month_start, month_end = _month_bounds(year, month)

    with _db_session_for_test() as db:
        # Osiguramo da tenant postoji
        ensure_tenant_exists(db, tenant)

        # Očistimo podatke za taj mjesec (da test bude determinističan)
        db.query(TaxMonthlyResult).filter(
            TaxMonthlyResult.tenant_code == tenant,
            TaxMonthlyResult.year == year,
            TaxMonthlyResult.month == month,
        ).delete()
        db.query(CashEntry).filter(
            CashEntry.tenant_code == tenant,
            CashEntry.entry_date >= month_start,
            CashEntry.entry_date < month_end,
        ).delete()
        db.query(Invoice).filter(
            Invoice.tenant_code == tenant,
            Invoice.issue_date >= month_start,
            Invoice.issue_date < month_end,
        ).delete()
        db.commit()

        # CASH (samo unutar mjeseca):
        # income: 100.00 + 50.00 = 150.00
        # expense: 40.00
        db.add_all(
            [
                CashEntry(
                    tenant_code=tenant,
                    entry_date=date(year, month, 10),
                    kind="income",
                    amount=Decimal("100.00"),
                    description="Prihod M1",
                ),
                CashEntry(
                    tenant_code=tenant,
                    entry_date=date(year, month, 15),
                    kind="income",
                    amount=Decimal("50.00"),
                    description="Prihod M2",
                ),
                CashEntry(
                    tenant_code=tenant,
                    entry_date=date(year, month, 20),
                    kind="expense",
                    amount=Decimal("40.00"),
                    description="Rashod M1",
                ),
            ]
        )

        # INVOICES (unutar mjeseca):
        # total_amount: 200.00 + 80.00 = 280.00
        inv1 = Invoice(
            tenant_code=tenant,
            invoice_number="DASH-M-INV-1",
            issue_date=date(year, month, 5),
            due_date=date(year, month, 25),
            buyer_name="Kupac M1",
            buyer_address="Adresa M1",
            total_base=Decimal("150.00"),
            total_vat=Decimal("50.00"),
            total_amount=Decimal("200.00"),
        )
        inv2 = Invoice(
            tenant_code=tenant,
            invoice_number="DASH-M-INV-2",
            issue_date=date(year, month, 18),
            due_date=None,
            buyer_name="Kupac M2",
            buyer_address=None,
            total_base=Decimal("80.00"),
            total_vat=Decimal("0.00"),
            total_amount=Decimal("80.00"),
        )
        db.add_all([inv1, inv2])

        # TAX MONTHLY RESULT za taj mjesec:
        # total_due: 300.00
        db.add(
            TaxMonthlyResult(
                tenant_code=tenant,
                year=year,
                month=month,
                total_income=Decimal("1000.00"),
                total_expense=Decimal("100.00"),
                taxable_base=Decimal("900.00"),
                income_tax=Decimal("90.00"),
                contributions_total=Decimal("210.00"),
                total_due=Decimal("300.00"),
                currency="BAM",
                is_final=True,
            )
        )

        db.commit()

    resp = client.get(
        f"/dashboard/monthly/{year}/{month}",
        headers={"X-Tenant-Code": tenant},
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["tenant_code"] == tenant
    assert data["year"] == year
    assert data["month"] == month

    # CASH
    cash = data["cash"]
    assert cash["year"] == year
    assert cash["month"] == month
    assert cash["income_total"] == "150.00"
    assert cash["expense_total"] == "40.00"
    assert cash["net_cashflow"] == "110.00"

    # INVOICES
    inv = data["invoices"]
    assert inv["year"] == year
    assert inv["month"] == month
    assert inv["invoices_count"] == 2
    assert inv["total_amount"] == "280.00"

    # TAX
    tax = data["tax"]
    assert tax["year"] == year
    assert tax["month"] == month
    assert tax["has_result"] is True
    assert tax["is_final"] is True
    assert tax["total_due"] == "300.00"


def test_dashboard_monthly_requires_tenant_header() -> None:
    """
    Bez X-Tenant-Code header-a mjesečni dashboard treba da vrati 400.
    """
    resp = client.get("/dashboard/monthly/2088/3")
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("detail") == "Missing X-Tenant-Code header"
