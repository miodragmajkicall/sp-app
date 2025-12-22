# /home/miso/dev/sp-app/sp-app/backend/tests/test_admin_constants_rollover.py

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import AppConstantsSet
from app.main import app


def _wipe_constants() -> None:
    db = SessionLocal()
    try:
        db.query(AppConstantsSet).delete()
        db.commit()
    finally:
        db.close()


def test_admin_constants_create_rollover_closes_previous_open_ended_only_same_scenario():
    _wipe_constants()
    client = TestClient(app)

    # 1) open-ended set od 2025-01-01
    r1 = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "vat": {"standard_rate": 0.17}},
            "created_by": "admin",
            "created_reason": "init",
        },
    )
    assert r1.status_code == 200, r1.text
    first = r1.json()
    assert first["effective_from"] == "2025-01-01"
    assert first["effective_to"] is None

    # 2) novi open-ended set od 2025-07-01 -> zatvara prvi na 2025-06-30
    r2 = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "RS",
            "scenario_key": "rs_primary",
            "effective_from": "2025-07-01",
            "effective_to": None,
            "payload": {"scenario_key": "rs_primary", "meta": {"v": 2}},
            "created_by": "admin",
            "created_reason": "update mid-year",
        },
    )
    assert r2.status_code == 200, r2.text

    # 3) lista
    rlist = client.get("/admin/constants", params={"jurisdiction": "RS", "scenario_key": "rs_primary"})
    assert rlist.status_code == 200, rlist.text
    items = rlist.json()["items"]
    assert len(items) >= 2

    by_from = {it["effective_from"]: it for it in items}
    assert by_from["2025-01-01"]["effective_to"] == "2025-06-30"
    assert by_from["2025-07-01"]["effective_to"] is None


def test_admin_constants_rollover_does_not_modify_bounded_sets_and_overlap_is_rejected_same_scenario():
    _wipe_constants()
    client = TestClient(app)

    # 1) bounded set
    r1 = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "FBiH",
            "scenario_key": "fbih_obrt",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "payload": {"scenario_key": "fbih_obrt"},
            "created_by": "admin",
            "created_reason": "init",
        },
    )
    assert r1.status_code == 200, r1.text

    # 2) overlap -> mora biti 400 (prethodni nije open-ended)
    r2 = client.post(
        "/admin/constants",
        json={
            "jurisdiction": "FBiH",
            "scenario_key": "fbih_obrt",
            "effective_from": "2025-06-01",
            "effective_to": None,
            "payload": {"scenario_key": "fbih_obrt", "meta": {"v": 2}},
            "created_by": "admin",
            "created_reason": "overlap attempt",
        },
    )
    assert r2.status_code == 400, r2.text
