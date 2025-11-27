from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.db import get_session as _get_session_dep
from app.models import TaxMonthlyResult

client = TestClient(app)


@contextmanager
def _db_session_for_test():
    """
    Helper context manager za direktan rad sa DB u testovima.

    Koristimo isti get_session dependency kao i API, ali ga ovdje
    ručno "vozimо" kao generator:
    - next() -> Session
    - drugi next() će pokrenuti finally blok i zatvoriti sesiju.
    """
    gen = _get_session_dep()
    db = next(gen)
    try:
        yield db
    finally:
        # Drugi next() pokreće finally blok u originalnom dependency-ju.
        try:
            next(gen)
        except StopIteration:
            pass


def test_sam_overview_path_registered_in_openapi() -> None:
    """
    Minimalni smoke-test za SAM domen u OpenAPI šemi.

    Cilj:
    - potvrditi da se bilo kakav SAM path pojavljuje u OpenAPI,
    - ne dirati DB niti poslovnu logiku u ovom testu.
    """
    resp = client.get("/openapi.json")
    assert resp.status_code == 200

    data = resp.json()
    paths = data.get("paths", {})

    sam_paths = [p for p in paths.keys() if p.startswith("/sam")]
    assert sam_paths, "Očekuje se bar jedan SAM endpoint u OpenAPI paths"


def test_sam_overview_default_structure_and_values() -> None:
    """
    Provjera osnovne strukture i podrazumijevanih (0.00) vrijednosti
    za SAM yearly overview endpoint u slučaju kada NE postoje tax
    rezultati za datu godinu.

    Koristimo godinu 2099 jer je vrlo mala vjerovatnoća da je koriste
    drugi testovi tax modula, pa samim tim očekujemo 'prazan' scenario.
    """
    year = 2099

    resp = client.get(
        f"/sam/overview/{year}",
        headers={"X-Tenant-Code": "t-demo"},
    )
    assert resp.status_code == 200

    data = resp.json()

    # osnovni metapodaci
    assert data["tenant_code"] == "t-demo"
    assert data["year"] == year

    # mjeseci
    months = data["months"]
    assert isinstance(months, list)
    assert len(months) == 12

    assert months[0]["month"] == 1
    assert months[-1]["month"] == 12

    for month in months:
        assert month["income_total"] == "0.00"
        assert month["expense_total"] == "0.00"
        assert month["tax_base"] == "0.00"
        assert month["tax_due"] == "0.00"
        assert month["contributions_due"] == "0.00"
        assert month["total_due"] == "0.00"
        # U scenariju bez tax_monthly_results svi mjeseci su ne-finalizovani
        assert month["is_finalized"] is False

    # godišnji sažetak
    summary = data["yearly_summary"]
    assert summary["year"] == year
    assert summary["income_total"] == "0.00"
    assert summary["expense_total"] == "0.00"
    assert summary["tax_base_total"] == "0.00"
    assert summary["tax_due_total"] == "0.00"
    assert summary["contributions_due_total"] == "0.00"
    assert summary["total_due"] == "0.00"
    assert summary["finalized_months"] == 0
    assert summary["open_months"] == 12


def test_sam_overview_with_real_tax_data() -> None:
    """
    Integration test: SAM overview spojen na realne podatke iz TAX modula.

    Koraci:
    - direktno upisujemo dva TaxMonthlyResult zapisa u bazu za tenant 't-demo'
      i godinu 2088 (godina koju drugi testovi vjerovatno ne koriste),
    - pozivamo /sam/overview/2088,
    - provjeravamo:
        * da su mjeseci 1 i 2 popunjeni tačnim vrijednostima,
        * da su ostali mjeseci 0.00 i ne-finalizovani,
        * da yearly_summary sadrži sumu ova dva mjeseca,
        * da se finalized/open mjeseci poklapaju sa očekivanim.
    """
    tenant_code = "t-demo"
    year = 2088

    # 1) Direct DB setup: čistimo potencijalne stare rezultate za (tenant, year)
    with _db_session_for_test() as db:
        db.query(TaxMonthlyResult).filter(
            TaxMonthlyResult.tenant_code == tenant_code,
            TaxMonthlyResult.year == year,
        ).delete()

        # Mjesec 1
        db.add(
            TaxMonthlyResult(
                tenant_code=tenant_code,
                year=year,
                month=1,
                total_income=Decimal("1000.00"),
                total_expense=Decimal("200.00"),
                taxable_base=Decimal("800.00"),
                income_tax=Decimal("80.00"),
                contributions_total=Decimal("120.00"),
                total_due=Decimal("200.00"),
                currency="BAM",
                is_final=True,
            )
        )

        # Mjesec 2
        db.add(
            TaxMonthlyResult(
                tenant_code=tenant_code,
                year=year,
                month=2,
                total_income=Decimal("500.00"),
                total_expense=Decimal("100.00"),
                taxable_base=Decimal("400.00"),
                income_tax=Decimal("40.00"),
                contributions_total=Decimal("60.00"),
                total_due=Decimal("100.00"),
                currency="BAM",
                is_final=True,
            )
        )

        db.commit()

    # 2) Pozivamo SAM overview endpoint
    resp = client.get(
        f"/sam/overview/{year}",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert resp.status_code == 200

    data = resp.json()

    # Metapodaci
    assert data["tenant_code"] == tenant_code
    assert data["year"] == year

    months = data["months"]
    assert isinstance(months, list)
    assert len(months) == 12

    # Mjesec 1
    m1 = months[0]
    assert m1["month"] == 1
    assert m1["income_total"] == "1000.00"
    assert m1["expense_total"] == "200.00"
    assert m1["tax_base"] == "800.00"
    assert m1["tax_due"] == "80.00"
    assert m1["contributions_due"] == "120.00"
    assert m1["total_due"] == "200.00"
    assert m1["is_finalized"] is True

    # Mjesec 2
    m2 = months[1]
    assert m2["month"] == 2
    assert m2["income_total"] == "500.00"
    assert m2["expense_total"] == "100.00"
    assert m2["tax_base"] == "400.00"
    assert m2["tax_due"] == "40.00"
    assert m2["contributions_due"] == "60.00"
    assert m2["total_due"] == "100.00"
    assert m2["is_finalized"] is True

    # Ostali mjeseci (3-12) su prazni i ne-finalizovani
    for month in months[2:]:
        assert month["income_total"] == "0.00"
        assert month["expense_total"] == "0.00"
        assert month["tax_base"] == "0.00"
        assert month["tax_due"] == "0.00"
        assert month["contributions_due"] == "0.00"
        assert month["total_due"] == "0.00"
        assert month["is_finalized"] is False

    # 3) Godišnji sažetak: suma prvog i drugog mjeseca
    summary = data["yearly_summary"]
    assert summary["year"] == year
    assert summary["income_total"] == "1500.00"          # 1000 + 500
    assert summary["expense_total"] == "300.00"          # 200 + 100
    assert summary["tax_base_total"] == "1200.00"        # 800 + 400
    assert summary["tax_due_total"] == "120.00"          # 80 + 40
    assert summary["contributions_due_total"] == "180.00"  # 120 + 60
    assert summary["total_due"] == "300.00"              # 200 + 100

    # finalized/open mjeseci
    assert summary["finalized_months"] == 2
    assert summary["open_months"] == 10
