# /home/miso/dev/sp-app/sp-app/backend/tests/test_settings.py
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_settings_profile_get_put():
    client = TestClient(app)

    res = client.get("/settings/profile", headers={"X-Tenant-Code": "t-demo"})
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_code"] == "t-demo"
    assert "business_name" in body

    res = client.put(
        "/settings/profile",
        headers={"X-Tenant-Code": "t-demo"},
        json={
            "business_name": "Miso SP",
            "address": "Banja Luka",
            "tax_id": "123456789",
            "logo_attachment_id": None,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_code"] == "t-demo"
    assert body["business_name"] == "Miso SP"
    assert body["address"] == "Banja Luka"
    assert body["tax_id"] == "123456789"
    assert body["logo_attachment_id"] is None


def _create_tenant(client: TestClient, prefix: str) -> dict[str, str]:
    code = f"{prefix}-{uuid4().hex[:8]}"
    response = client.post("/tenants", json={"code": code, "name": prefix})
    assert response.status_code == 201, response.text
    return {"X-Tenant-Code": code}


def test_profile_contact_and_bank_fields_round_trip_and_normalization():
    client = TestClient(app)
    headers = _create_tenant(client, "profile-full")
    expected = {
        "phone": "+387 51 123 456",
        "email": "office@example.ba",
        "bank_name": "Test Banka",
        "bank_account": "555-123-99",
        "iban": "BA391290079401028494",
        "swift_bic": "TESTBA22",
    }
    response = client.put(
        "/settings/profile",
        headers=headers,
        json={
            "business_name": "Test SP",
            **{field: f"  {value}  " for field, value in expected.items()},
        },
    )
    assert response.status_code == 200, response.text
    for field, value in expected.items():
        assert response.json()[field] == value
        assert client.get("/settings/profile", headers=headers).json()[field] == value


def test_profile_partial_values_and_blank_normalization():
    client = TestClient(app)
    headers = _create_tenant(client, "profile-partial")
    response = client.put(
        "/settings/profile",
        headers=headers,
        json={
            "business_name": "Partial SP",
            "phone": "  051/123-456 ",
            "email": "   ",
            "bank_name": "",
            "bank_account": "\t",
            "iban": "  ",
            "swift_bic": "\n",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phone"] == "051/123-456"
    for field in ("email", "bank_name", "bank_account", "iban", "swift_bic"):
        assert body[field] is None


@pytest.mark.parametrize(
    ("field", "max_length"),
    [
        ("phone", 64),
        ("email", 254),
        ("bank_name", 128),
        ("bank_account", 128),
        ("iban", 64),
        ("swift_bic", 32),
    ],
)
def test_profile_rejects_values_over_limit(field: str, max_length: int):
    client = TestClient(app)
    headers = _create_tenant(client, f"profile-limit-{field}")
    response = client.put(
        "/settings/profile",
        headers=headers,
        json={"business_name": "Limit SP", field: "x" * (max_length + 1)},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "email",
    [
        "@example.ba",
        "office@",
        "office@example",
        "office@.example.ba",
        "office@example.ba.",
        "off ice@example.ba",
        "office@example .ba",
        "office@@example.ba",
    ],
)
def test_profile_rejects_invalid_email(email: str):
    client = TestClient(app)
    headers = _create_tenant(client, "profile-email")
    response = client.put(
        "/settings/profile",
        headers=headers,
        json={"business_name": "Email SP", "email": email},
    )
    assert response.status_code == 422


def test_profile_is_isolated_between_tenants():
    client = TestClient(app)
    first_headers = _create_tenant(client, "profile-tenant-a")
    second_headers = _create_tenant(client, "profile-tenant-b")
    first = client.put(
        "/settings/profile",
        headers=first_headers,
        json={"business_name": "Tenant A", "email": "a@example.ba"},
    )
    second = client.put(
        "/settings/profile",
        headers=second_headers,
        json={"business_name": "Tenant B", "email": "b@example.ba"},
    )
    assert first.status_code == second.status_code == 200
    assert client.get("/settings/profile", headers=first_headers).json()["email"] == "a@example.ba"
    assert client.get("/settings/profile", headers=second_headers).json()["email"] == "b@example.ba"


def test_profile_put_preserves_omitted_optional_fields_and_clears_explicit_null():
    client = TestClient(app)
    headers = _create_tenant(client, "profile-patch")
    created = client.put(
        "/settings/profile",
        headers=headers,
        json={
            "business_name": "Patch SP",
            "phone": "+387 51 555 555",
            "email": "patch@example.ba",
            "bank_name": "Patch Banka",
        },
    )
    assert created.status_code == 200, created.text

    omitted = client.put(
        "/settings/profile",
        headers=headers,
        json={"business_name": "Patch SP Updated"},
    )
    assert omitted.status_code == 200, omitted.text
    assert omitted.json()["phone"] == "+387 51 555 555"
    assert omitted.json()["email"] == "patch@example.ba"
    assert omitted.json()["bank_name"] == "Patch Banka"

    cleared = client.put(
        "/settings/profile",
        headers=headers,
        json={"business_name": "Patch SP Updated", "email": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["email"] is None
    assert cleared.json()["phone"] == "+387 51 555 555"
    assert cleared.json()["bank_name"] == "Patch Banka"


def test_settings_tax_profile():
    client = TestClient(app)

    res = client.put(
        "/settings/tax",
        headers={"X-Tenant-Code": "t-demo"},
        json={
            "entity": "RS",
            "regime": "pausal",
            "has_additional_activity": False,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_code"] == "t-demo"
    assert body["entity"] == "RS"
    assert body["regime"] == "pausal"
    assert body["has_additional_activity"] is False


def test_settings_subscription():
    client = TestClient(app)

    res = client.put(
        "/settings/subscription",
        headers={"X-Tenant-Code": "t-demo"},
        json={"plan": "Premium"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_code"] == "t-demo"
    assert body["plan"] == "Premium"
