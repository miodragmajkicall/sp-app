from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import TenantTaxProfileSettings
from app.services.tax_profile_scenario import (
    TenantTaxScenarioIntegrityError,
    normalize_tenant_tax_jurisdiction,
    validate_tenant_tax_scenario,
)


client = TestClient(app)


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        ("RS", "RS"),
        ("FBiH", "FBiH"),
        ("Brcko", "BD"),
        ("Brčko", "BD"),
        ("BD", "BD"),
    ],
)
def test_normalize_tenant_tax_jurisdiction(entity: str, expected: str) -> None:
    assert normalize_tenant_tax_jurisdiction(entity) == expected


@pytest.mark.parametrize(
    ("has_additional_activity", "scenario_key"),
    [
        (False, "rs_primary"),
        (True, "rs_supplementary"),
    ],
)
def test_rs_scenario_matches_tenant_fact(
    has_additional_activity: bool,
    scenario_key: str,
) -> None:
    assert (
        validate_tenant_tax_scenario(
            jurisdiction="RS",
            scenario_key=scenario_key,
            has_additional_activity=has_additional_activity,
            require_explicit=True,
        )
        == scenario_key
    )


@pytest.mark.parametrize(
    ("has_additional_activity", "scenario_key"),
    [
        (False, "rs_supplementary"),
        (True, "rs_primary"),
    ],
)
def test_rs_scenario_fact_mismatch_is_rejected(
    has_additional_activity: bool,
    scenario_key: str,
) -> None:
    with pytest.raises(
        TenantTaxScenarioIntegrityError,
        match="conflicts with has_additional_activity",
    ) as exc_info:
        validate_tenant_tax_scenario(
            jurisdiction="RS",
            scenario_key=scenario_key,
            has_additional_activity=has_additional_activity,
            require_explicit=True,
        )

    assert exc_info.value.code == "tax_profile_scenario_fact_mismatch"


@pytest.mark.parametrize(
    ("jurisdiction", "scenario_key"),
    [
        ("FBiH", "fbih_obrt"),
        ("FBiH", "fbih_slobodna"),
        ("BD", "bd_samostalna"),
    ],
)
def test_supported_non_rs_scenarios_are_explicitly_allowed(
    jurisdiction: str,
    scenario_key: str,
) -> None:
    assert (
        validate_tenant_tax_scenario(
            jurisdiction=jurisdiction,
            scenario_key=scenario_key,
            has_additional_activity=False,
            require_explicit=True,
        )
        == scenario_key
    )


def test_verified_profile_requires_explicit_scenario() -> None:
    with pytest.raises(TenantTaxScenarioIntegrityError) as exc_info:
        validate_tenant_tax_scenario(
            jurisdiction="RS",
            scenario_key=None,
            has_additional_activity=False,
            require_explicit=True,
        )

    assert exc_info.value.code == "tax_profile_scenario_missing"


def test_legacy_unverified_profile_may_remain_without_scenario() -> None:
    assert (
        validate_tenant_tax_scenario(
            jurisdiction="RS",
            scenario_key=None,
            has_additional_activity=False,
            require_explicit=False,
        )
        is None
    )


def test_settings_rejects_verified_rs_scenario_fact_mismatch() -> None:
    tenant = f"tax-scenario-mismatch-{uuid4().hex[:10]}"
    headers = {"X-Tenant-Code": tenant}

    response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": True,
            "effective_from": "2026-01-01",
        },
    )

    assert response.status_code == 409, response.text
    assert "tax_profile_scenario_fact_mismatch" in response.json()["detail"]


def test_settings_rejects_verified_profile_without_scenario() -> None:
    tenant = f"tax-scenario-missing-{uuid4().hex[:10]}"
    headers = {"X-Tenant-Code": tenant}

    response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": None,
            "has_additional_activity": False,
            "effective_from": "2026-01-01",
        },
    )

    assert response.status_code == 409, response.text
    assert "tax_profile_scenario_missing" in response.json()["detail"]


def test_settings_rejects_scenario_from_other_jurisdiction() -> None:
    tenant = f"tax-scenario-jurisdiction-{uuid4().hex[:10]}"
    headers = {"X-Tenant-Code": tenant}

    response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": "FBiH",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
            "effective_from": "2026-01-01",
        },
    )

    assert response.status_code == 409, response.text
    assert (
        "tax_profile_scenario_jurisdiction_mismatch"
        in response.json()["detail"]
    )


def test_tax_live_resolver_rejects_historical_rs_fact_mismatch() -> None:
    tenant = f"tax-corrupt-scenario-{uuid4().hex[:10]}"
    headers = {"X-Tenant-Code": tenant}

    create_response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
            "effective_from": "2026-01-01",
        },
    )
    assert create_response.status_code == 200, create_response.text

    # Simulate a legacy/direct-DB corruption that bypassed the Settings API.
    with SessionLocal() as db:
        row = db.execute(
            select(TenantTaxProfileSettings).where(
                TenantTaxProfileSettings.tenant_code == tenant,
                TenantTaxProfileSettings.effective_to.is_(None),
            )
        ).scalar_one()

        row.has_additional_activity = True
        db.commit()

    response = client.get(
        "/tax/monthly/preview",
        headers=headers,
        params={
            "year": 2026,
            "month": 1,
            "total_income": "1000.00",
            "total_expense": "0.00",
        },
    )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "tax_profile_scenario_fact_mismatch" in detail
    assert "has_additional_activity=True" in detail

def test_tax_ui_schema_rejects_verified_rs_fact_mismatch() -> None:
    tenant = f"tax-ui-corrupt-scenario-{uuid4().hex[:10]}"
    headers = {"X-Tenant-Code": tenant}

    create_response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": "RS",
            "regime": "pausal",
            "scenario_key": "rs_primary",
            "has_additional_activity": False,
            "effective_from": "2026-01-01",
        },
    )
    assert create_response.status_code == 200, create_response.text

    # Simulate legacy/direct-DB corruption that bypassed Settings validation.
    with SessionLocal() as db:
        row = db.execute(
            select(TenantTaxProfileSettings).where(
                TenantTaxProfileSettings.tenant_code == tenant,
                TenantTaxProfileSettings.effective_to.is_(None),
            )
        ).scalar_one()

        row.has_additional_activity = True
        db.commit()

    response = client.get(
        "/settings/tax/ui-schema",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "tax_profile_scenario_fact_mismatch" in detail
    assert "has_additional_activity=True" in detail
