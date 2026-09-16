# /home/miso/dev/sp-app/sp-app/backend/tests/test_admin_constants.py
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db import SessionLocal


def _wipe_constants():
    s = SessionLocal()
    try:
        s.execute(text("DELETE FROM app_constants_sets"))
        s.commit()
    finally:
        s.close()


def test_admin_constants_create_and_current():
    _wipe_constants()
    client = TestClient(app)

    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "payload": {"scenario_key": "rs_primary", "vat": {"standard_rate": 0.17}},
            "created_by": "tester",
            "created_reason": "init RS 2025",
        },
    )
    assert res.status_code == 200
    created = res.json()
    assert created["jurisdiction"] == "RS"
    assert created["scenario_key"] == "rs_primary"
    assert created["effective_from"] == "2025-01-01"
    assert created["effective_to"] == "2025-12-31"
    assert created["payload"]["vat"]["standard_rate"] == 0.17

    # current in mid-2025 -> found
    res = client.get(
        "/constants/current",
        params={"jurisdiction": "RS", "scenario_key": "rs_primary", "as_of": "2025-06-10"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["jurisdiction"] == "RS"
    assert body["scenario_key"] == "rs_primary"
    assert body["as_of"] == "2025-06-10"
    assert body["found"] is True
    assert body["item"]["id"] == created["id"]

    # current before 2025 -> not found
    res = client.get(
        "/constants/current",
        params={"jurisdiction": "RS", "scenario_key": "rs_primary", "as_of": "2024-12-31"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is False
    assert body["item"] is None


def test_admin_constants_overlap_rejected_within_same_scenario():
    _wipe_constants()
    client = TestClient(app)

    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "payload": {"scenario_key": "rs_primary", "x": 1},
            "created_by": "tester",
            "created_reason": "init RS 2025",
        },
    )
    assert res.status_code == 200

    # Overlap within same scenario
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-06-01",
            "effective_to": "2026-01-01",
            "payload": {"scenario_key": "rs_primary", "x": 2},
            "created_by": "tester",
            "created_reason": "overlap attempt",
        },
    )
    assert res.status_code == 400
    assert "Overlapping" in res.json()["detail"]


def test_admin_constants_overlap_allowed_across_different_scenarios():
    _wipe_constants()
    client = TestClient(app)

    r1 = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "payload": {"scenario_key": "rs_primary", "x": 1},
            "created_by": "tester",
            "created_reason": "init primary",
        },
    )
    assert r1.status_code == 200, r1.text

    # Same dates, different scenario -> allowed
    r2 = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_supplementary",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "payload": {"scenario_key": "rs_supplementary", "x": 2},
            "created_by": "tester",
            "created_reason": "init supplementary",
        },
    )
    assert r2.status_code == 200, r2.text


def test_admin_constants_update_changes_payload_and_audit():
    _wipe_constants()
    client = TestClient(app)

    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "vat": {"standard_rate": 0.17}},
            "created_by": "tester",
            "created_reason": "init RS open-ended",
        },
    )
    assert res.status_code == 200
    created = res.json()
    cid = created["id"]

    res = client.put(
        f"/admin/constants/{cid}",
        json={
            "payload": {"scenario_key": "rs_primary", "vat": {"standard_rate": 0.20}},
            "updated_by": "tester2",
            "updated_reason": "change rate",
        },
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["id"] == cid
    assert updated["payload"]["vat"]["standard_rate"] == 0.20
    assert updated["updated_by"] == "tester2"
    assert updated["updated_reason"] == "change rate"


def test_admin_constants_create_with_rollover_closes_previous_and_creates_new_same_scenario():
    _wipe_constants()
    client = TestClient(app)

    # 1) Open-ended set from 2025-01-01
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "tax": {"flat_costs_rate": 0.3}},
            "created_by": "admin",
            "created_reason": "init",
        },
    )
    assert res.status_code == 200
    first = res.json()
    assert first["effective_from"] == "2025-01-01"
    assert first["effective_to"] is None

    # 2) New set starting 2025-07-01
    res = client.post(
        "/admin/constants",
        params={"rollover": "true"},  # ignored by backend; kept for back-compat
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-07-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "tax": {"flat_costs_rate": 0.25}},
            "created_by": "admin",
            "created_reason": "mid-year change",
        },
    )
    assert res.status_code == 200
    second = res.json()
    assert second["effective_from"] == "2025-07-01"
    assert second["effective_to"] is None

    # 3) List -> previous must be closed to 2025-06-30
    res = client.get("/admin/constants", params={"jurisdiction": "RS", "scenario_key": "rs_primary"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 2

    by_id = {it["id"]: it for it in items}
    assert by_id[first["id"]]["effective_to"] == "2025-06-30"

    # 4) current check before/after rollover point
    res = client.get(
        "/constants/current",
        params={"jurisdiction": "RS", "scenario_key": "rs_primary", "as_of": "2025-06-10"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is True
    assert body["item"]["id"] == first["id"]

    res = client.get(
        "/constants/current",
        params={"jurisdiction": "RS", "scenario_key": "rs_primary", "as_of": "2025-07-10"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is True
    assert body["item"]["id"] == second["id"]


# -----------------------------
# New semantic validation tests
# -----------------------------


def test_admin_constants_rejects_rate_out_of_bounds():
    _wipe_constants()
    client = TestClient(app)

    # vat.standard_rate must be 0..1
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "vat": {"standard_rate": 1.70}},
            "created_by": "tester",
            "created_reason": "invalid vat rate",
        },
    )
    assert res.status_code == 400, res.text
    assert "vat.standard_rate" in res.json()["detail"]


def test_admin_constants_rejects_negative_rate():
    _wipe_constants()
    client = TestClient(app)

    # tax.income_tax_rate must be 0..1
    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "tax": {"income_tax_rate": -0.10}},
            "created_by": "tester",
            "created_reason": "invalid income tax rate",
        },
    )
    assert res.status_code == 400, res.text
    assert "tax.income_tax_rate" in res.json()["detail"]


def test_admin_constants_rs_base_calculation_mismatch_allowed_input_only_payload():
    _wipe_constants()
    client = TestClient(app)

    # Input-only payload: backend does NOT enforce calculated_contrib_base_bam matching avg*(percent/100)
    # (computed logic is handled outside constants payload definition).
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
                    "avg_gross_wage_prev_year_bam": 2000.0,
                    "contrib_base_percent_of_avg_gross": 80.0,
                    "calculated_contrib_base_bam": 1000.0,  # intentionally "mismatch"
                },
                "vat": {"standard_rate": 0.17},
            },
            "created_by": "tester",
            "created_reason": "rs base mismatch allowed",
        },
    )
    assert res.status_code == 200, res.text
    created = res.json()
    assert created["payload"]["base"]["avg_gross_wage_prev_year_bam"] == 2000.0
    assert created["payload"]["base"]["contrib_base_percent_of_avg_gross"] == 80.0
    assert created["payload"]["base"]["calculated_contrib_base_bam"] == 1000.0


def test_admin_constants_fbih_monthly_base_must_be_positive():
    _wipe_constants()
    client = TestClient(app)

    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "FBiH",
            "scenario_key": "fbih_obrt",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "scenario_key": "fbih_obrt",
                "base": {"monthly_contrib_base_bam": 0},
            },
            "created_by": "tester",
            "created_reason": "fbih base invalid",
        },
    )
    assert res.status_code == 400, res.text
    assert "base.monthly_contrib_base_bam" in res.json()["detail"]


def test_admin_constants_bd_percent_bounds_rejected():
    _wipe_constants()
    client = TestClient(app)

    res = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "BD",
            "scenario_key": "bd_samostalna",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {
                "scenario_key": "bd_samostalna",
                "base": {
                    "avg_gross_prev_year_bam": 2000.0,
                    "base_percent_of_avg_gross": 120.0,  # invalid (>100)
                    "calculated_contrib_base_bam": 2400.0,
                },
            },
            "created_by": "tester",
            "created_reason": "bd percent invalid",
        },
    )
    assert res.status_code == 400, res.text
    assert "base.base_percent_of_avg_gross" in res.json()["detail"]


def _canonical_rs_primary_payload() -> dict:
    return {
        "schema_version": "legal-constants-v1",
        "scenario_key": "rs_primary",
        "base": {
            "currency": "BAM",
            "avg_gross_wage_prev_year_bam": 2000,
            "contrib_base_percent_of_avg_gross": 80,
            "calculated_contrib_base_bam": 1600,
        },
        "tax": {
            "income_tax_rate": 0.10,
            "flat_costs_rate": 0,
            "flat_tax_monthly_amount_bam": 0,
        },
        "contributions": {
            "pension_rate": 0.18,
            "health_rate": 0.12,
            "unemployment_rate": 0.015,
        },
        "vat": {
            "standard_rate": 0.17,
            "entry_threshold_bam": 0,
        },
        "meta": {
            "source_note": "typed contract test",
            "source_reference": "test",
        },
    }


def test_admin_constants_create_accepts_canonical_versioned_payload():
    _wipe_constants()
    client = TestClient(app)

    response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "payload": _canonical_rs_primary_payload(),
            "created_by": "tester",
            "created_reason": "canonical typed payload",
        },
    )

    assert response.status_code == 200, response.text

    created = response.json()
    assert created["payload"]["schema_version"] == "legal-constants-v1"
    assert created["payload"]["scenario_key"] == "rs_primary"
    assert created["payload"]["tax"]["flat_costs_rate"] == 0
    assert created["payload"]["vat"]["entry_threshold_bam"] == 0


def test_admin_constants_create_rejects_unknown_declared_schema_version():
    _wipe_constants()
    client = TestClient(app)

    payload = _canonical_rs_primary_payload()
    payload["schema_version"] = "legal-constants-v999"

    response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "payload": payload,
            "created_by": "tester",
            "created_reason": "invalid schema version",
        },
    )

    assert response.status_code == 400, response.text
    assert "schema_version" in response.json()["detail"]


def test_admin_constants_create_rejects_canonical_payload_scenario_mismatch():
    _wipe_constants()
    client = TestClient(app)

    payload = _canonical_rs_primary_payload()
    payload["scenario_key"] = "rs_supplementary"

    response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "payload": payload,
            "created_by": "tester",
            "created_reason": "scenario mismatch",
        },
    )

    assert response.status_code == 400, response.text
    assert "must match outer scenario_key" in response.json()["detail"]


def test_admin_constants_create_rejects_unknown_canonical_field():
    _wipe_constants()
    client = TestClient(app)

    payload = _canonical_rs_primary_payload()
    payload["tax"]["invented_rate"] = 0.25

    response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "payload": payload,
            "created_by": "tester",
            "created_reason": "unknown field",
        },
    )

    assert response.status_code == 400, response.text
    assert "invented_rate" in response.json()["detail"]


def test_admin_constants_legacy_payload_without_schema_version_remains_supported():
    _wipe_constants()
    client = TestClient(app)

    response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "payload": {
                "scenario_key": "rs_primary",
                "tax": {
                    "income_tax_rate": 0.10,
                    "flat_costs_rate": 0.30,
                },
            },
            "created_by": "tester",
            "created_reason": "legacy compatibility",
        },
    )

    assert response.status_code == 200, response.text
    assert "schema_version" not in response.json()["payload"]


def test_admin_constants_update_validates_complete_canonical_candidate_before_mutation():
    _wipe_constants()
    client = TestClient(app)

    create_response = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "payload": _canonical_rs_primary_payload(),
            "created_by": "tester",
            "created_reason": "canonical original",
        },
    )
    assert create_response.status_code == 200, create_response.text

    constants_id = create_response.json()["id"]

    # Outer scenario change without matching canonical payload must fail.
    update_response = client.put(
        f"/admin/constants/{constants_id}",
        json={
            "scenario_key": "rs_supplementary",
            "updated_by": "tester2",
            "updated_reason": "invalid outer-only scenario change",
        },
    )

    assert update_response.status_code == 400, update_response.text
    assert "must match outer scenario_key" in update_response.json()["detail"]

    # Failed validation must not partially mutate the stored row.
    list_response = client.get(
        "/admin/constants",
        params={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
        },
    )
    assert list_response.status_code == 200, list_response.text

    items = list_response.json()["items"]
    stored = next(item for item in items if item["id"] == constants_id)

    assert stored["scenario_key"] == "rs_primary"
    assert stored["payload"]["scenario_key"] == "rs_primary"
