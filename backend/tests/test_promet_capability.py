from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
)


def _create_tenant(
    client: TestClient,
    prefix: str,
) -> dict[str, str]:
    code = f"{prefix}-{uuid4().hex[:8]}"
    response = client.post(
        "/tenants",
        json={"code": code, "name": prefix},
    )
    assert response.status_code == 201, response.text
    return {"X-Tenant-Code": code}


def _put_tax_profile(
    client: TestClient,
    headers: dict[str, str],
    *,
    entity: str,
    regime: str,
    scenario_key: str,
) -> None:
    response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": entity,
            "regime": regime,
            "scenario_key": scenario_key,
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert response.status_code == 200, response.text


def test_promet_capability_missing_profiles_is_read_only() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-empty")
    tenant_code = headers["X-Tenant-Code"]

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "tenant_code": tenant_code,
        "status": "needs_configuration",
        "mode": None,
        "reason_code": "unsupported_or_missing_entity",
        "blocking_fields": ["entity"],
    }

    db = SessionLocal()
    try:
        tax_profile = db.execute(
            select(TenantTaxProfileSettings).where(
                TenantTaxProfileSettings.tenant_code == tenant_code
            )
        ).scalar_one_or_none()

        business_profile = db.execute(
            select(TenantBusinessProfileSettings).where(
                TenantBusinessProfileSettings.tenant_code == tenant_code
            )
        ).scalar_one_or_none()

        assert tax_profile is None
        assert business_profile is None
    finally:
        db.close()


def test_promet_capability_unknown_tenant_does_not_create_it() -> None:
    client = TestClient(app)
    missing_code = f"capability-missing-{uuid4().hex[:8]}"

    response = client.get(
        "/settings/business/promet-capability",
        headers={"X-Tenant-Code": missing_code},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"

    tenants_response = client.get("/tenants")
    assert tenants_response.status_code == 200
    assert all(
        tenant["code"] != missing_code
        for tenant in tenants_response.json()
    )


def test_promet_capability_rs_two_percent_needs_no_business_profile() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-rs")

    _put_tax_profile(
        client,
        headers,
        entity="RS",
        regime="two_percent",
        scenario_key="rs_primary",
    )

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applicable"
    assert body["mode"] == "rs_small_entrepreneur"
    assert body["reason_code"] == "rs_small_entrepreneur_promet"
    assert body["blocking_fields"] == []


def test_promet_capability_fbih_pausal_missing_b2b_fact() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-fbih-missing")

    _put_tax_profile(
        client,
        headers,
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
    )

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "needs_configuration"
    assert body["mode"] is None
    assert body["reason_code"] == "fbih_pausal_b2b_status_missing"
    assert body["blocking_fields"] == [
        "has_noncash_sales_to_legal_entities"
    ]


def test_promet_capability_fbih_pausal_b2b_is_applicable() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-fbih-b2b")

    _put_tax_profile(
        client,
        headers,
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
    )

    business_response = client.put(
        "/settings/business",
        headers=headers,
        json={"has_noncash_sales_to_legal_entities": True},
    )
    assert business_response.status_code == 200, business_response.text

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applicable"
    assert body["mode"] == "fbih_kp1042_pausal_b2b"
    assert body["blocking_fields"] == []


def test_promet_capability_fbih_books_multi_location_is_applicable() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-fbih-books")

    _put_tax_profile(
        client,
        headers,
        entity="FBiH",
        regime="books",
        scenario_key="fbih_obrt",
    )

    business_response = client.put(
        "/settings/business",
        headers=headers,
        json={
            "sales_locations_count": 2,
            "sells_to_consumers": True,
            "daily_cash_turnover_covered_elsewhere": False,
        },
    )
    assert business_response.status_code == 200, business_response.text

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applicable"
    assert body["mode"] == "fbih_kp1042_multi_location"
    assert body["reason_code"] == "fbih_books_multi_location_kp1042"


def test_promet_capability_is_isolated_between_tenants() -> None:
    client = TestClient(app)
    rs_headers = _create_tenant(client, "capability-tenant-rs")
    fbih_headers = _create_tenant(client, "capability-tenant-fbih")

    _put_tax_profile(
        client,
        rs_headers,
        entity="RS",
        regime="two_percent",
        scenario_key="rs_primary",
    )
    _put_tax_profile(
        client,
        fbih_headers,
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
    )

    rs_response = client.get(
        "/settings/business/promet-capability",
        headers=rs_headers,
    )
    fbih_response = client.get(
        "/settings/business/promet-capability",
        headers=fbih_headers,
    )

    assert rs_response.status_code == 200, rs_response.text
    assert fbih_response.status_code == 200, fbih_response.text

    assert rs_response.json()["status"] == "applicable"
    assert rs_response.json()["mode"] == "rs_small_entrepreneur"

    assert fbih_response.json()["status"] == "needs_configuration"
    assert fbih_response.json()["mode"] is None
    assert fbih_response.json()["blocking_fields"] == [
        "has_noncash_sales_to_legal_entities"
    ]

def test_promet_capability_corrupt_rs_fact_mismatch_needs_configuration() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-rs-corrupt")
    tenant_code = headers["X-Tenant-Code"]

    _put_tax_profile(
        client,
        headers,
        entity="RS",
        regime="two_percent",
        scenario_key="rs_primary",
    )

    with SessionLocal() as db:
        row = db.execute(
            select(TenantTaxProfileSettings).where(
                TenantTaxProfileSettings.tenant_code == tenant_code,
                TenantTaxProfileSettings.effective_to.is_(None),
            )
        ).scalar_one()
        row.has_additional_activity = True
        db.commit()

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "needs_configuration"
    assert body["mode"] is None
    assert body["reason_code"] == "tax_profile_scenario_fact_mismatch"
    assert body["blocking_fields"] == [
        "scenario_key",
        "has_additional_activity",
    ]


def test_promet_capability_corrupt_cross_jurisdiction_scenario_needs_configuration() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "capability-fbih-corrupt")
    tenant_code = headers["X-Tenant-Code"]

    _put_tax_profile(
        client,
        headers,
        entity="FBiH",
        regime="books",
        scenario_key="fbih_obrt",
    )

    with SessionLocal() as db:
        row = db.execute(
            select(TenantTaxProfileSettings).where(
                TenantTaxProfileSettings.tenant_code == tenant_code,
                TenantTaxProfileSettings.effective_to.is_(None),
            )
        ).scalar_one()
        row.scenario_key = "rs_primary"
        db.commit()

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "needs_configuration"
    assert body["mode"] is None
    assert body["reason_code"] == "tax_profile_scenario_jurisdiction_mismatch"
    assert body["blocking_fields"] == ["scenario_key"]
