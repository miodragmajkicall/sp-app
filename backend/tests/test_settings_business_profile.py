from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_tenant(client: TestClient, prefix: str) -> dict[str, str]:
    code = f"{prefix}-{uuid4().hex[:8]}"
    response = client.post(
        "/tenants",
        json={"code": code, "name": prefix},
    )
    assert response.status_code == 201, response.text
    return {"X-Tenant-Code": code}


def test_business_profile_get_returns_unconfigured_defaults() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "business-default")

    response = client.get("/settings/business", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_code"] == headers["X-Tenant-Code"]
    assert body["sales_locations_count"] is None
    assert body["sells_to_consumers"] is None
    assert body["daily_cash_turnover_covered_elsewhere"] is None
    assert body["has_noncash_sales_to_legal_entities"] is None


def test_business_profile_full_round_trip() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "business-full")
    payload = {
        "sales_locations_count": 2,
        "sells_to_consumers": True,
        "daily_cash_turnover_covered_elsewhere": False,
        "has_noncash_sales_to_legal_entities": True,
    }

    put_response = client.put(
        "/settings/business",
        headers=headers,
        json=payload,
    )

    assert put_response.status_code == 200, put_response.text
    put_body = put_response.json()
    assert put_body["tenant_code"] == headers["X-Tenant-Code"]

    for field_name, expected in payload.items():
        assert put_body[field_name] == expected

    get_response = client.get("/settings/business", headers=headers)
    assert get_response.status_code == 200, get_response.text

    get_body = get_response.json()
    for field_name, expected in payload.items():
        assert get_body[field_name] == expected


def test_business_profile_put_preserves_omitted_and_clears_explicit_null() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "business-patch")

    created = client.put(
        "/settings/business",
        headers=headers,
        json={
            "sales_locations_count": 2,
            "sells_to_consumers": True,
            "daily_cash_turnover_covered_elsewhere": False,
            "has_noncash_sales_to_legal_entities": True,
        },
    )
    assert created.status_code == 200, created.text

    partial = client.put(
        "/settings/business",
        headers=headers,
        json={"sales_locations_count": 3},
    )
    assert partial.status_code == 200, partial.text
    partial_body = partial.json()

    assert partial_body["sales_locations_count"] == 3
    assert partial_body["sells_to_consumers"] is True
    assert partial_body["daily_cash_turnover_covered_elsewhere"] is False
    assert partial_body["has_noncash_sales_to_legal_entities"] is True

    cleared = client.put(
        "/settings/business",
        headers=headers,
        json={"has_noncash_sales_to_legal_entities": None},
    )
    assert cleared.status_code == 200, cleared.text
    cleared_body = cleared.json()

    assert cleared_body["sales_locations_count"] == 3
    assert cleared_body["sells_to_consumers"] is True
    assert cleared_body["daily_cash_turnover_covered_elsewhere"] is False
    assert cleared_body["has_noncash_sales_to_legal_entities"] is None


def test_business_profile_rejects_negative_sales_locations_count() -> None:
    client = TestClient(app)
    headers = _create_tenant(client, "business-negative")

    response = client.put(
        "/settings/business",
        headers=headers,
        json={"sales_locations_count": -1},
    )

    assert response.status_code == 422


def test_business_profile_is_isolated_between_tenants() -> None:
    client = TestClient(app)
    first_headers = _create_tenant(client, "business-a")
    second_headers = _create_tenant(client, "business-b")

    first = client.put(
        "/settings/business",
        headers=first_headers,
        json={
            "sales_locations_count": 1,
            "sells_to_consumers": True,
        },
    )
    second = client.put(
        "/settings/business",
        headers=second_headers,
        json={
            "sales_locations_count": 4,
            "sells_to_consumers": False,
        },
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    first_body = client.get(
        "/settings/business",
        headers=first_headers,
    ).json()
    second_body = client.get(
        "/settings/business",
        headers=second_headers,
    ).json()

    assert first_body["sales_locations_count"] == 1
    assert first_body["sells_to_consumers"] is True

    assert second_body["sales_locations_count"] == 4
    assert second_body["sells_to_consumers"] is False


def test_business_profile_unknown_tenant_get_is_read_only() -> None:
    client = TestClient(app)
    missing_code = f"business-missing-{uuid4().hex[:8]}"

    response = client.get(
        "/settings/business",
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
