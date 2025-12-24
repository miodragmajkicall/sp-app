# /home/miso/dev/sp-app/sp-app/backend/tests/test_settings.py
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
