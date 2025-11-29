from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, select

from app.main import app
from app.db import SessionLocal
from app.routes.tax import TAX_DUMMY_CONFIG

client = TestClient(app)


def _ensure_tenant(db, tenant_code: str) -> None:
    """
    Kreira tenanta u tabeli tenants ako već ne postoji.

    Koristi refleksiju SQLAlchemy nad tabelom `tenants` kako bi bio robustan
    na eventualne promjene šeme.

    VAŽNO: kolona `id` je String(32), pa ovdje pazimo da vrijednost
    bude kraća ili jednaka 32 znaka.
    """
    bind = db.get_bind()
    metadata = MetaData()
    tenants = Table("tenants", metadata, autoload_with=bind)

    existing = db.execute(
        tenants.select().where(tenants.c.code == tenant_code)
    ).first()
    if existing:
        return

    row: dict = {}
    for col in tenants.columns:
        if col.name == "id":
            # Kratak, jedinstven ID, max 32 znaka
            row[col.name] = (f"taxfin-{tenant_code}")[:32]
        elif col.name == "code":
            row[col.name] = tenant_code
        elif col.name == "name":
            row[col.name] = "Tenant za tax finalize test"
        elif (
            not col.nullable
            and col.server_default is None
            and col.default is None
            and col.name not in row
        ):
            python_type = getattr(col.type, "python_type", str)
            if python_type is str:
                row[col.name] = "dummy"
            elif python_type is int:
                row[col.name] = 1
            elif python_type is float:
                row[col.name] = 1.0
            elif python_type is Decimal:
                row[col.name] = Decimal("1.00")
            elif python_type.__name__ == "date":
                row[col.name] = date(2025, 1, 1)
            else:
                row[col.name] = "dummy"

    db.execute(tenants.insert().values(**row))


def _insert_invoice_january_2025(
    db, *, tenant_code: str, total_amount: Decimal
) -> None:
    """
    Ubacuje jednu fakturu u tabelu `invoices` za januar 2025.

    Koristi refleksiju nad tabelom kako bi popunio obavezne kolone.
    """
    bind = db.get_bind()
    metadata = MetaData()
    invoices = Table("invoices", metadata, autoload_with=bind)

    row: dict = {}
    for col in invoices.columns:
        if col.name == "id":
            # pretpostavljamo autoincrement / identity – ne diramo
            continue
        elif col.name == "tenant_code":
            row[col.name] = tenant_code
        elif col.name == "issue_date":
            row[col.name] = date(2025, 1, 5)
        elif col.name == "total_amount":
            row[col.name] = total_amount
        elif (
            not col.nullable
            and col.server_default is None
            and col.default is None
            and col.name not in row
        ):
            python_type = getattr(col.type, "python_type", str)
            if python_type is str:
                # tipično: number, currency, status, sl.
                row[col.name] = "dummy"
            elif python_type is int:
                row[col.name] = 1
            elif python_type is float:
                row[col.name] = 1.0
            elif python_type is Decimal:
                row[col.name] = Decimal("1.00")
            elif python_type.__name__ == "date":
                row[col.name] = date(2025, 1, 1)
            else:
                row[col.name] = "dummy"

    db.execute(invoices.insert().values(**row))


def _insert_cash_entry_january_2025(
    db, *, tenant_code: str, kind: str, amount: Decimal
) -> None:
    """
    Ubacuje jedan zapis u `cash_entries` za januar 2025.
    """
    bind = db.get_bind()
    metadata = MetaData()
    cash_entries = Table("cash_entries", metadata, autoload_with=bind)

    row: dict = {}
    for col in cash_entries.columns:
        if col.name == "id":
            # pretpostavljamo identity/autoincrement
            continue
        elif col.name == "tenant_code":
            row[col.name] = tenant_code
        elif col.name == "entry_date":
            row[col.name] = date(2025, 1, 10)
        elif col.name == "kind":
            row[col.name] = kind
        elif col.name == "amount":
            row[col.name] = amount
        elif col.name == "description":
            row[col.name] = f"{kind} for tax finalize test"
        elif (
            not col.nullable
            and col.server_default is None
            and col.default is None
            and col.name not in row
        ):
            python_type = getattr(col.type, "python_type", str)
            if python_type is str:
                row[col.name] = "dummy"
            elif python_type is int:
                row[col.name] = 1
            elif python_type is float:
                row[col.name] = 1.0
            elif python_type is Decimal:
                row[col.name] = Decimal("1.00")
            elif python_type.__name__ == "date":
                row[col.name] = date(2025, 1, 1)
            else:
                row[col.name] = "dummy"

    db.execute(cash_entries.insert().values(**row))


def _cleanup_tax_test_data(db, tenant_code: str) -> None:
    """
    Briše sve što smo ubacili za datog tenanta iz:
    - tax_monthly_results
    - cash_entries
    - invoices
    - tenants
    """
    bind = db.get_bind()
    metadata = MetaData()

    tax_results = Table("tax_monthly_results", metadata, autoload_with=bind)
    cash_entries = Table("cash_entries", metadata, autoload_with=bind)
    invoices = Table("invoices", metadata, autoload_with=bind)
    tenants = Table("tenants", metadata, autoload_with=bind)

    db.execute(
        tax_results.delete().where(tax_results.c.tenant_code == tenant_code)
    )
    db.execute(
        cash_entries.delete().where(cash_entries.c.tenant_code == tenant_code)
    )
    db.execute(
        invoices.delete().where(invoices.c.tenant_code == tenant_code)
    )
    db.execute(tenants.delete().where(tenants.c.code == tenant_code))
    db.commit()


def _dec2(value) -> Decimal:
    """
    Pomoćna funkcija za zaokruživanje na 2 decimale (BAM).
    """
    return Decimal(str(value)).quantize(Decimal("0.01"))


def test_tax_monthly_finalize_persists_result_and_marks_final() -> None:
    """
    Testira da:
    - /tax/monthly/finalize računa iste vrijednosti kao DUMMY formula
    - rezultat se zapisuje u tax_monthly_results
    - is_final je True
    - /tax/monthly/auto nakon finalizacije vraća persistirani rezultat
    """
    tenant_code = "t-tax-finalize-1"

    db = SessionLocal()
    try:
        _ensure_tenant(db, tenant_code)

        invoice_income = Decimal("1000.00")
        cash_income = Decimal("200.00")
        cash_expense = Decimal("150.00")

        _insert_invoice_january_2025(
            db, tenant_code=tenant_code, total_amount=invoice_income
        )
        _insert_cash_entry_january_2025(
            db,
            tenant_code=tenant_code,
            kind="income",
            amount=cash_income,
        )
        _insert_cash_entry_january_2025(
            db,
            tenant_code=tenant_code,
            kind="expense",
            amount=cash_expense,
        )
        db.commit()

        headers = {"X-Tenant-Code": tenant_code}
        params = {"year": 2025, "month": 1}

        # 1) Finalizacija
        resp = client.post("/tax/monthly/finalize", params=params, headers=headers)
        assert resp.status_code == 200

        data = resp.json()

        cfg = TAX_DUMMY_CONFIG

        total_income = invoice_income + cash_income
        total_expense = cash_expense

        # DUMMY formula – ista kao u _compute_monthly_summary
        flat_costs = total_income * cfg.flat_costs_rate
        taxable_base = total_income - flat_costs - total_expense
        if taxable_base < Decimal("0"):
            taxable_base = Decimal("0.00")

        income_tax = taxable_base * cfg.income_tax_rate
        contrib_rate_sum = (
            cfg.pension_contribution_rate
            + cfg.health_contribution_rate
            + cfg.unemployment_contribution_rate
        )
        contributions_total = taxable_base * contrib_rate_sum
        total_due = income_tax + contributions_total

        # 1a) Provjera response payload-a
        assert data["year"] == 2025
        assert data["month"] == 1
        assert data["tenant_code"] == tenant_code
        assert data["is_final"] is True
        assert data["currency"] == cfg.currency

        assert _dec2(data["total_income"]) == _dec2(total_income)
        assert _dec2(data["total_expense"]) == _dec2(total_expense)
        assert _dec2(data["taxable_base"]) == _dec2(taxable_base)
        assert _dec2(data["income_tax"]) == _dec2(income_tax)
        assert _dec2(data["contributions_total"]) == _dec2(contributions_total)
        assert _dec2(data["total_due"]) == _dec2(total_due)

        # 1b) Provjera da je zapis u bazi
        bind = db.get_bind()
        metadata = MetaData()
        tax_results = Table("tax_monthly_results", metadata, autoload_with=bind)

        row = db.execute(
            select(tax_results).where(
                tax_results.c.tenant_code == tenant_code,
                tax_results.c.year == 2025,
                tax_results.c.month == 1,
            )
        ).first()
        assert row is not None

        assert _dec2(row.total_income) == _dec2(total_income)
        assert _dec2(row.total_expense) == _dec2(total_expense)
        assert _dec2(row.taxable_base) == _dec2(taxable_base)
        assert _dec2(row.income_tax) == _dec2(income_tax)
        assert _dec2(row.contributions_total) == _dec2(contributions_total)
        assert _dec2(row.total_due) == _dec2(total_due)
        assert row.currency == cfg.currency
        assert row.is_final is True

        # 1c) /tax/monthly/auto nakon finalizacije treba da vrati isti, finalizovan rezultat
        resp_auto = client.get("/tax/monthly/auto", params=params, headers=headers)
        assert resp_auto.status_code == 200
        data_auto = resp_auto.json()

        assert data_auto["is_final"] is True
        assert _dec2(data_auto["total_income"]) == _dec2(total_income)
        assert _dec2(data_auto["total_expense"]) == _dec2(total_expense)
        assert _dec2(data_auto["taxable_base"]) == _dec2(taxable_base)
        assert _dec2(data_auto["income_tax"]) == _dec2(income_tax)
        assert _dec2(data_auto["contributions_total"]) == _dec2(contributions_total)
        assert _dec2(data_auto["total_due"]) == _dec2(total_due)

    finally:
        _cleanup_tax_test_data(db, tenant_code)
        db.close()


def test_tax_monthly_finalize_cannot_double_finalize_same_period() -> None:
    """
    Testira da drugi poziv na /tax/monthly/finalize za isti (tenant, year, month)
    vraća 400 i ne pravi dupli zapis.
    """
    tenant_code = "t-tax-finalize-2"

    db = SessionLocal()
    try:
        _ensure_tenant(db, tenant_code)

        invoice_income = Decimal("500.00")
        cash_income = Decimal("100.00")
        cash_expense = Decimal("50.00")

        _insert_invoice_january_2025(
            db, tenant_code=tenant_code, total_amount=invoice_income
        )
        _insert_cash_entry_january_2025(
            db,
            tenant_code=tenant_code,
            kind="income",
            amount=cash_income,
        )
        _insert_cash_entry_january_2025(
            db,
            tenant_code=tenant_code,
            kind="expense",
            amount=cash_expense,
        )
        db.commit()

        headers = {"X-Tenant-Code": tenant_code}
        params = {"year": 2025, "month": 1}

        # Prvi put treba da prođe
        resp_1 = client.post("/tax/monthly/finalize", params=params, headers=headers)
        assert resp_1.status_code == 200

        # Drugi put mora da padne sa 400
        resp_2 = client.post("/tax/monthly/finalize", params=params, headers=headers)
        assert resp_2.status_code == 400

        data_err = resp_2.json()
        assert (
            data_err.get("detail")
            == "Monthly tax result for this period is already finalized"
        )

        # U bazi i dalje treba da postoji samo jedan zapis
        bind = db.get_bind()
        metadata = MetaData()
        tax_results = Table("tax_monthly_results", metadata, autoload_with=bind)

        rows = db.execute(
            select(tax_results).where(
                tax_results.c.tenant_code == tenant_code,
                tax_results.c.year == 2025,
                tax_results.c.month == 1,
            )
        ).fetchall()
        assert len(rows) == 1

    finally:
        _cleanup_tax_test_data(db, tenant_code)
        db.close()
