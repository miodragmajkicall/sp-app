# /home/miso/dev/sp-app/sp-app/backend/tests/test_tax_constants_integration.py
from decimal import Decimal

import pytest
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


@pytest.fixture(autouse=True)
def _isolate_tax_constants_integration_state():
    _wipe_tables()
    try:
        yield
    finally:
        _wipe_tables()


def _d(v) -> Decimal:
    return Decimal(str(v))


def _canonical_policy(
    scenario_key: str,
    *,
    income_tax_rate: float,
    pension_rate: float,
    health_rate: float,
    unemployment_rate: float,
    flat_costs_rate: float = 0.0,
    currency: str = "BAM",
) -> dict:
    return {
        "schema_version": "legal-constants-v1",
        "scenario_key": scenario_key,
        "base": {
            "currency": currency,
        },
        "tax": {
            "income_tax_rate": income_tax_rate,
            "flat_costs_rate": flat_costs_rate,
        },
        "contributions": {
            "pension_rate": pension_rate,
            "health_rate": health_rate,
            "unemployment_rate": unemployment_rate,
        },
    }


def test_tax_preview_uses_canonical_admin_constants_policy():
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
            "payload": _canonical_policy(
                "rs_primary",
                income_tax_rate=0.20,
                pension_rate=0.10,
                health_rate=0.05,
                unemployment_rate=0.01,
                flat_costs_rate=0.00,
            ),
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
            "effective_from": "2025-01-01",
            "regime": "pausal",
            "scenario_key": "rs_primary",
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


def test_tax_settings_cannot_override_canonical_admin_constants_policy():
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
            "payload": _canonical_policy(
                "rs_primary",
                income_tax_rate=0.20,
                pension_rate=0.10,
                health_rate=0.05,
                unemployment_rate=0.01,
                flat_costs_rate=0.00,
            ),
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
            "effective_from": "2025-01-01",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert res.status_code == 200, res.text

    # Legacy /tax/settings may still exist, but it must not override
    # the verified canonical Admin Constants policy.
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

    # Canonical Admin Constants remain authoritative:
    # taxable_base=1000, income_tax=200 despite legacy tenant TaxSettings=10%.
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
    assert _d(body["income_tax"]) == Decimal("200.00")
    assert _d(body["contributions_total"]) == Decimal("160.00")
    assert _d(body["total_due"]) == Decimal("360.00")
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
            "payload": _canonical_policy(
                "rs_primary",
                income_tax_rate=0.20,
                pension_rate=0.10,
                health_rate=0.05,
                unemployment_rate=0.01,
                flat_costs_rate=0.00,
            ),
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
            "payload": _canonical_policy(
                "rs_supplementary",
                income_tax_rate=0.08,
                pension_rate=0.07,
                health_rate=0.00,
                unemployment_rate=0.00,
                flat_costs_rate=0.00,
            ),
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
            "effective_from": "2025-01-01",
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


def test_tax_preview_supports_canonical_legal_constants_v1_payload():
    _wipe_tables()
    client = TestClient(app)

    tenant = "t-const-v2"

    # Canonical legal-constants-v1 policy.
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": _canonical_policy(
                "rs_primary",
                income_tax_rate=0.15,
                pension_rate=0.09,
                health_rate=0.04,
                unemployment_rate=0.01,
                flat_costs_rate=0.00,
            ),
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
            "effective_from": "2025-01-01",
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


def test_tax_preview_rejects_legacy_unversioned_constants_payload():
    _wipe_tables()
    client = TestClient(app)

    tenant = "t-const-legacy-rejected"

    create_response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            # Structurally consumable by the old parser, but intentionally
            # missing schema_version and therefore legacy/unverified.
            "payload": {
                "scenario_key": "rs_primary",
                "base": {
                    "currency": "BAM",
                },
                "tax": {
                    "income_tax_rate": 0.15,
                    "flat_costs_rate": 0.00,
                },
                "contributions": {
                    "pension_rate": 0.09,
                    "health_rate": 0.04,
                    "unemployment_rate": 0.01,
                },
            },
            "created_by": "tester",
            "created_reason": "legacy unversioned policy rejection fixture",
        },
    )
    assert create_response.status_code == 200, create_response.text

    profile_response = client.put(
        "/settings/tax",
        headers={"X-Tenant-Code": tenant},
        json={
            "entity": "RS",
            "effective_from": "2025-01-01",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert profile_response.status_code == 200, profile_response.text

    response = client.get(
        "/tax/monthly/preview",
        headers={"X-Tenant-Code": tenant},
        params={
            "year": 2025,
            "month": 1,
            "total_income": "1000.00",
            "total_expense": "0.00",
        },
    )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "legacy/unverified" in detail
    assert "schema_version=legal-constants-v1" in detail
