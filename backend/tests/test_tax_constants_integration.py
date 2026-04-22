# /home/miso/dev/sp-app/sp-app/backend/tests/test_tax_constants_integration.py
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db import SessionLocal


def _wipe_tables():
    s = SessionLocal()
    try:
        # order matters zbog FK-ova
        s.execute(text("DELETE FROM tax_settings"))
        s.execute(text("DELETE FROM tenant_tax_profile_settings"))
        s.execute(text("DELETE FROM tenant_profile_settings"))
        s.execute(text("DELETE FROM tenant_subscription_settings"))
        s.execute(text("DELETE FROM app_constants_sets"))
        s.execute(text("DELETE FROM tenants"))
        s.commit()
    finally:
        s.close()


def _d(v) -> Decimal:
    return Decimal(str(v))


def test_tax_preview_uses_app_constants_set_when_no_tax_settings_override():
    _wipe_tables()
    client = TestClient(app)

    tenant = "t-const-1"

    # 1) Kreiraj constants set za RS (2025) - V1 scenario: RS primary
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "tax": {
                    "income_tax_rate": 0.20,
                    "pension_contribution_rate": 0.10,
                    "health_contribution_rate": 0.05,
                    "unemployment_contribution_rate": 0.01,
                    "flat_costs_rate": 0.00,
                    "currency": "BAM",
                }
            },
            "created_by": "tester",
            "created_reason": "RS tax constants 2025+",
        },
    )
    assert res.status_code == 200, res.text

    # 2) Postavi tenant tax profile -> RS
    res = client.put(
        "/settings/tax",
        headers={"X-Tenant-Code": tenant},
        json={
            "entity": "RS",
            "regime": "pausal",
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert res.status_code == 200, res.text

    # 3) Preview za Jan 2025: total_income=1000, total_expense=0
    res = client.get(
        "/tax/monthly/preview",
        headers={"X-Tenant-Code": tenant},
        params={
            "year": 2025,
            "month": 1,
            "total_income": "1000.00",
            "total_expense": "0.00",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    # taxable_base = 1000
    assert _d(body["taxable_base"]) == Decimal("1000.00")

    # income_tax = 1000 * 0.20 = 200
    assert _d(body["income_tax"]) == Decimal("200.00")

    # contributions_total = 1000*(0.10+0.05+0.01)=160
    assert _d(body["contributions_total"]) == Decimal("160.00")

    # total_due = 360
    assert _d(body["total_due"]) == Decimal("360.00")
    assert body["currency"] == "BAM"


def test_tax_settings_override_beats_app_constants_set():
    _wipe_tables()
    client = TestClient(app)

    tenant = "t-const-2"

    # constants set: income_tax_rate=0.20 (RS primary)
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "tax": {
                    "income_tax_rate": 0.20,
                    "pension_contribution_rate": 0.10,
                    "health_contribution_rate": 0.05,
                    "unemployment_contribution_rate": 0.01,
                    "flat_costs_rate": 0.00,
                    "currency": "BAM",
                }
            },
            "created_by": "tester",
            "created_reason": "RS tax constants 2025+",
        },
    )
    assert res.status_code == 200, res.text

    # settings/tax -> RS
    res = client.put(
        "/settings/tax",
        headers={"X-Tenant-Code": tenant},
        json={
            "entity": "RS",
            "regime": "pausal",
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert res.status_code == 200, res.text

    # upsert /tax/settings override: income_tax_rate=0.10 (pregazi constants)
    res = client.put(
        "/tax/settings",
        headers={"X-Tenant-Code": tenant},
        json={
            "income_tax_rate": "0.10",
            "pension_contribution_rate": "0.10",
            "health_contribution_rate": "0.05",
            "unemployment_contribution_rate": "0.01",
            "flat_costs_rate": "0.00",
            "currency": "BAM",
        },
    )
    assert res.status_code == 200, res.text

    # preview: taxable_base=1000, income_tax=100 (ne 200)
    res = client.get(
        "/tax/monthly/preview",
        headers={"X-Tenant-Code": tenant},
        params={
            "year": 2025,
            "month": 1,
            "total_income": "1000.00",
            "total_expense": "0.00",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert _d(body["taxable_base"]) == Decimal("1000.00")
    assert _d(body["income_tax"]) == Decimal("100.00")  # override pobjeđuje
    assert _d(body["contributions_total"]) == Decimal("160.00")
    assert _d(body["total_due"]) == Decimal("260.00")
    assert body["currency"] == "BAM"


def test_tax_preview_uses_matching_scenario_key_when_multiple_sets_exist():
    _wipe_tables()
    client = TestClient(app)

    tenant = "t-const-scenario"

    # RS primary set
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "tax": {
                    "income_tax_rate": 0.20,
                    "pension_contribution_rate": 0.10,
                    "health_contribution_rate": 0.05,
                    "unemployment_contribution_rate": 0.01,
                    "flat_costs_rate": 0.00,
                    "currency": "BAM",
                }
            },
            "created_by": "tester",
            "created_reason": "RS primary constants",
        },
    )
    assert res.status_code == 200, res.text

    # RS supplementary set
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_supplementary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "tax": {
                    "income_tax_rate": 0.08,
                    "pension_contribution_rate": 0.07,
                    "health_contribution_rate": 0.00,
                    "unemployment_contribution_rate": 0.00,
                    "flat_costs_rate": 0.00,
                    "currency": "BAM",
                }
            },
            "created_by": "tester",
            "created_reason": "RS supplementary constants",
        },
    )
    assert res.status_code == 200, res.text

    # Tenant eksplicitno koristi supplementary scenario
    res = client.put(
        "/settings/tax",
        headers={"X-Tenant-Code": tenant},
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": "rs_supplementary",
            "has_additional_activity": True,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert res.status_code == 200, res.text

    res = client.get(
        "/tax/monthly/preview",
        headers={"X-Tenant-Code": tenant},
        params={
            "year": 2025,
            "month": 1,
            "total_income": "1000.00",
            "total_expense": "0.00",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    # mora uzeti supplementary, ne primary
    assert _d(body["taxable_base"]) == Decimal("1000.00")
    assert _d(body["income_tax"]) == Decimal("80.00")
    assert _d(body["contributions_total"]) == Decimal("70.00")
    assert _d(body["total_due"]) == Decimal("150.00")
    assert body["currency"] == "BAM"


def test_tax_preview_supports_v2_constants_payload_shape():
    _wipe_tables()
    client = TestClient(app)

    tenant = "t-const-v2"

    # V2 payload: tax + contributions + base.currency
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "scenario_key": "rs_primary",
                "base": {
                    "currency": "BAM",
                    "avg_gross_wage_prev_year_bam": 2000,
                    "contrib_base_percent_of_avg_gross": 80,
                },
                "tax": {
                    "income_tax_rate": 0.15,
                    "flat_tax_monthly_amount_bam": None,
                    "flat_costs_rate": 0.00,
                },
                "contributions": {
                    "pension_rate": 0.09,
                    "health_rate": 0.04,
                    "unemployment_rate": 0.01,
                },
            },
            "created_by": "tester",
            "created_reason": "RS primary V2 payload",
        },
    )
    assert res.status_code == 200, res.text

    res = client.put(
        "/settings/tax",
        headers={"X-Tenant-Code": tenant},
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert res.status_code == 200, res.text

    res = client.get(
        "/tax/monthly/preview",
        headers={"X-Tenant-Code": tenant},
        params={
            "year": 2025,
            "month": 1,
            "total_income": "1000.00",
            "total_expense": "0.00",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    # taxable_base = 1000
    assert _d(body["taxable_base"]) == Decimal("1000.00")

    # income_tax = 1000 * 0.15 = 150
    assert _d(body["income_tax"]) == Decimal("150.00")

    # contributions_total = 1000 * (0.09 + 0.04 + 0.01) = 140
    assert _d(body["contributions_total"]) == Decimal("140.00")

    # total_due = 290
    assert _d(body["total_due"]) == Decimal("290.00")
    assert body["currency"] == "BAM"