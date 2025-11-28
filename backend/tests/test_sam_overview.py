from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _d0(value: object) -> Decimal:
    """
    Helper koji JSON vrijednosti (string, int, float) pretvara u Decimal,
    da ne zavisimo od formata serijalizacije ("0.0", "0.00", 0, itd.).
    """
    return Decimal(str(value))


def test_sam_overview_empty_year_returns_12_zero_months() -> None:
    """
    Ako za tenanta i godinu ne postoji nijedan zapis u tax_monthly_results,
    SAM overview treba da vrati:

    - 12 mjeseci,
    - sve vrijednosti po mjesecu = 0.00,
    - is_finalized = False za sve mjesece,
    - yearly_summary total-i = 0.00,
    - finalized_months = 0, open_months = 12.
    """
    tenant_code = "sam-tenant-empty"
    year = 2025

    resp = client.get(
        f"/sam/overview/{year}",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["tenant_code"] == tenant_code
    assert data["year"] == year

    months = data["months"]
    assert isinstance(months, list)
    assert len(months) == 12

    # Provjerimo da imamo mjesece 1..12 i da su svi 0.00 / not finalized
    seen_months = set()

    for item in months:
        m = item["month"]
        seen_months.add(m)
        assert 1 <= m <= 12

        assert _d0(item["income_total"]) == Decimal("0")
        assert _d0(item["expense_total"]) == Decimal("0")
        assert _d0(item["tax_base"]) == Decimal("0")
        assert _d0(item["tax_due"]) == Decimal("0")
        assert _d0(item["contributions_due"]) == Decimal("0")
        assert _d0(item["total_due"]) == Decimal("0")
        assert item["is_finalized"] is False

    assert seen_months == set(range(1, 13))

    yearly = data["yearly_summary"]
    assert yearly["year"] == year
    assert _d0(yearly["income_total"]) == Decimal("0")
    assert _d0(yearly["expense_total"]) == Decimal("0")
    assert _d0(yearly["tax_base_total"]) == Decimal("0")
    assert _d0(yearly["tax_due_total"]) == Decimal("0")
    assert _d0(yearly["contributions_due_total"]) == Decimal("0")
    assert _d0(yearly["total_due"]) == Decimal("0")
    assert yearly["finalized_months"] == 0
    assert yearly["open_months"] == 12


def test_sam_overview_with_one_finalized_month_uses_tax_monthly_results() -> None:
    """
    Scenarij:

    - koristimo postojećeg tenanta 't-demo' (postoji u tabeli tenants),
    - radimo sa godinom 2099 i mjesecom 3 da se minimalno sudaramo sa drugim testovima,
    - ako mjesec NIJE finalizovan:
        - pozivamo /tax/monthly/finalize i koristimo taj rezultat,
    - ako mjesec VEĆ jeste finalizovan:
        - preskačemo finalize i čitamo postojeći rezultat preko /tax/monthly/auto.

    U oba slučaja provjeravamo:

    - da je taj mjesec u SAM overview označen kao is_finalized = True,
    - da total_due za taj mjesec u SAM overview odgovara onom iz tax modula,
    - da yearly_summary.total_due = suma total_due za svih 12 mjeseci,
    - da finalized_months + open_months = 12.
    """
    tenant_code = "t-demo"
    year = 2099
    month = 3
    headers = {"X-Tenant-Code": tenant_code}

    # 1) Pokušamo finalize za (year, month, tenant)
    finalize_resp = client.post(
        f"/tax/monthly/finalize?year={year}&month={month}",
        headers=headers,
    )

    if finalize_resp.status_code == 200:
        # Svjež finalize – direktno koristimo rezultat
        finalized = finalize_resp.json()
    else:
        # Ako je već finalizovano, očekujemo baš ovu poruku iz finalize endpointa
        body = finalize_resp.json()
        assert (
            finalize_resp.status_code == 400
        ), f"Unexpected status from finalize: {finalize_resp.status_code}, body={body}"
        assert body.get("detail") == "Monthly tax result for this period is already finalized"

        # U tom slučaju, čitamo već postojeći rezultat kroz /tax/monthly/auto
        auto_resp = client.get(
            f"/tax/monthly/auto?year={year}&month={month}",
            headers=headers,
        )
        assert auto_resp.status_code == 200, auto_resp.text
        finalized = auto_resp.json()

    finalized_total_due = _d0(finalized["total_due"])

    # 2) SAM overview za istu godinu i tenanta
    resp = client.get(
        f"/sam/overview/{year}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["tenant_code"] == tenant_code
    assert data["year"] == year

    months = data["months"]
    assert len(months) == 12

    finalized_flags: dict[int, bool] = {}
    total_due_by_month: dict[int, Decimal] = {}

    for item in months:
        m = item["month"]
        finalized_flags[m] = bool(item["is_finalized"])
        total_due_by_month[m] = _d0(item["total_due"])

    # Naš konkretan mjesec mora biti finalizovan
    assert finalized_flags[month] is True

    # I total_due u SAM overview-u za taj mjesec mora biti isti kao iz tax modula
    assert total_due_by_month[month] == finalized_total_due

    # Yearly summary treba da sabira svih 12 mjeseci
    yearly = data["yearly_summary"]
    assert yearly["year"] == year

    expected_total_due = sum(total_due_by_month.values(), Decimal("0"))
    assert _d0(yearly["total_due"]) == expected_total_due

    # finalizovani mjeseci u yearly_summary moraju se poklapati sa onim što smo dobili iz months
    finalized_months_count = sum(1 for v in finalized_flags.values() if v)
    assert yearly["finalized_months"] == finalized_months_count
    assert yearly["open_months"] == 12 - finalized_months_count

    # Osiguramo da je barem jedan mjesec finalizovan (naš)
    assert finalized_months_count >= 1


def test_sam_overview_requires_tenant_header() -> None:
    """
    Negativni scenario:

    - pozovemo /sam/overview/{year} bez X-Tenant-Code header-a,
    - očekujemo 400 + poruku koju zaista vraća globalni tenant security helper
      (trenutno: 'Missing X-Tenant-Code header').
    """
    year = 2025

    resp = client.get(f"/sam/overview/{year}")
    assert resp.status_code == 400
    body = resp.json()
    # Poruka mora da se poklapa sa stvarnom validacijom koja važi globalno
    assert body.get("detail") == "Missing X-Tenant-Code header"
