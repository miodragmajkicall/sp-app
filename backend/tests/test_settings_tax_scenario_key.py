# /home/miso/dev/sp-app/sp-app/backend/tests/test_settings_tax_scenario_key.py
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models import AppConstantsSet


@pytest.fixture()
def client() -> TestClient:
    # Lokalni TestClient fixture (u ovom repo-u globalni "client" fixture ne postoji)
    return TestClient(app)


def _cleanup_constants_for_scenarios() -> None:
    db = SessionLocal()
    try:
        db.query(AppConstantsSet).filter(
            AppConstantsSet.jurisdiction.in_(["RS", "FBiH", "BD"]),
            AppConstantsSet.scenario_key.in_(
                [
                    "rs_primary",
                    "rs_supplementary",
                    "fbih_obrt",
                    "fbih_slobodna",
                    "bd_samostalna",
                ]
            ),
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _insert_rs_primary_constants() -> None:
    db = SessionLocal()
    try:
        row = AppConstantsSet(
            jurisdiction="RS",
            scenario_key="rs_primary",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            created_reason="test settings ui schema resolved values",
            payload={
                "scenario_key": "rs_primary",
                "base": {
                    "currency": "BAM",
                    "avg_gross_wage_prev_year_bam": 2100.0,
                    "contrib_base_percent_of_avg_gross": 60.0,
                    "calculated_contrib_base_bam": 1260.0,
                },
                "contributions": {
                    "pension_rate": 0.18,
                    "health_rate": 0.12,
                    "unemployment_rate": 0.015,
                    "child_rate": 0.017,
                },
                "tax": {
                    "income_tax_rate": 0.10,
                    "flat_tax_monthly_amount_bam": 50.0,
                },
                "vat": {
                    "standard_rate": 0.17,
                    "entry_threshold_bam": 50000.0,
                },
            },
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _upsert_tax_profile_rs_primary(client: TestClient) -> None:
    payload = {
        "entity": "RS",
        "regime": "pausal",
        "scenario_key": "rs_primary",
        "has_additional_activity": False,
        "monthly_pension": None,
        "monthly_health": None,
        "monthly_unemployment": None,
    }
    res = client.put("/settings/tax", json=payload, headers={"X-Tenant-Code": "t-demo"})
    assert res.status_code == 200


def test_get_settings_tax_includes_scenario_key(client: TestClient):
    res = client.get("/settings/tax", headers={"X-Tenant-Code": "t-demo"})
    assert res.status_code == 200
    data = res.json()
    assert "scenario_key" in data


def test_put_settings_tax_persists_scenario_key(client: TestClient):
    payload = {
        "entity": "RS",
        "regime": "pausal",
        "scenario_key": "rs_primary",
        "has_additional_activity": False,
        "monthly_pension": None,
        "monthly_health": None,
        "monthly_unemployment": None,
    }
    res = client.put("/settings/tax", json=payload, headers={"X-Tenant-Code": "t-demo"})
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_key"] == "rs_primary"

    # roundtrip
    res2 = client.get("/settings/tax", headers={"X-Tenant-Code": "t-demo"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["scenario_key"] == "rs_primary"


def test_get_settings_tax_scenarios_catalog_rs(client: TestClient):
    res = client.get("/settings/tax/scenarios?entity=RS&has_additional_activity=false")
    assert res.status_code == 200
    arr = res.json()
    assert isinstance(arr, list)
    assert len(arr) >= 1
    assert arr[0]["key"] in ("rs_primary", "rs_supplementary")


def test_get_settings_tax_ui_schema_returns_resolved_values_from_active_constants_set(
    client: TestClient,
):
    _cleanup_constants_for_scenarios()
    _insert_rs_primary_constants()
    _upsert_tax_profile_rs_primary(client)

    res = client.get(
        "/settings/tax/ui-schema?as_of=2026-04-23",
        headers={"X-Tenant-Code": "t-demo"},
    )
    assert res.status_code == 200

    data = res.json()
    assert data["entity"] == "RS"
    assert data["scenario_key"] == "rs_primary"
    assert data["constants_currency"] == "BAM"
    assert data["constants_set_id"] is not None
    assert data["constants_effective_from"] == "2026-01-01"
    assert data["resolved_values"]

    resolved_by_key = {item["key"]: item for item in data["resolved_values"]}

    assert resolved_by_key["base.currency"]["value"] == "BAM"
    assert resolved_by_key["base.avg_gross_wage_prev_year_bam"]["value"] == "2100.00 BAM"
    assert resolved_by_key["base.contrib_base_percent_of_avg_gross"]["value"] == "60.00%"
    assert resolved_by_key["base.calculated_contrib_base_bam"]["value"] == "1260.00 BAM"

    assert resolved_by_key["contributions.pension_rate"]["value"] == "18.00%"
    assert resolved_by_key["contributions.health_rate"]["value"] == "12.00%"
    assert resolved_by_key["contributions.unemployment_rate"]["value"] == "1.50%"
    assert resolved_by_key["contributions.child_rate"]["value"] == "1.70%"

    assert resolved_by_key["tax.income_tax_rate"]["value"] == "10.00%"
    assert resolved_by_key["tax.flat_tax_monthly_amount_bam"]["value"] == "50.00 BAM"

    assert resolved_by_key["vat.standard_rate"]["value"] == "17.00%"
    assert resolved_by_key["vat.entry_threshold_bam"]["value"] == "50000.00 BAM"


def test_get_settings_tax_ui_schema_returns_empty_resolved_values_when_no_active_constants_set(
    client: TestClient,
):
    _cleanup_constants_for_scenarios()
    _upsert_tax_profile_rs_primary(client)

    res = client.get(
        "/settings/tax/ui-schema?as_of=2026-04-23",
        headers={"X-Tenant-Code": "t-demo"},
    )
    assert res.status_code == 200

    data = res.json()
    assert data["entity"] == "RS"
    assert data["scenario_key"] == "rs_primary"
    assert data["constants_set_id"] is None
    assert data["constants_effective_from"] is None
    assert data["constants_effective_to"] is None
    assert data["constants_currency"] == "BAM"
    assert data["resolved_values"] == []


def test_get_settings_tax_ui_schema_rejects_invalid_as_of(client: TestClient):
    res = client.get(
        "/settings/tax/ui-schema?as_of=2026-99-99",
        headers={"X-Tenant-Code": "t-demo"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid as_of. Expected YYYY-MM-DD."