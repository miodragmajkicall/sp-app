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
