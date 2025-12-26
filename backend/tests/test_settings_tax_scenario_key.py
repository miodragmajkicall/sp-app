# /home/miso/dev/sp-app/sp-app/backend/tests/test_settings_tax_scenario_key.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    # Lokalni TestClient fixture (u ovom repo-u globalni "client" fixture ne postoji)
    return TestClient(app)


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
