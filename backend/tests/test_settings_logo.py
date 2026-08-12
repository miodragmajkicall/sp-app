# /home/miso/dev/sp-app/sp-app/backend/tests/test_settings_logo.py
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routes import settings as settings_routes


# Minimalni 1x1 PNG (transparent) – validan PNG fajl
MIN_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_settings_profile_logo_upload_get_delete(tmp_path: Path, monkeypatch):
    # usmjeri storage u tmp
    monkeypatch.setattr(settings_routes, "TENANT_ASSETS_ROOT", tmp_path / "tenant_assets")

    client = TestClient(app)
    headers = {"X-Tenant-Code": "t-demo"}

    # upload
    files = {"file": ("logo.png", MIN_PNG, "image/png")}
    r = client.post("/settings/profile/logo", headers=headers, files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tenant_code"] == "t-demo"
    assert body.get("logo_asset_id") is not None

    # get/preview
    r2 = client.get("/settings/profile/logo", headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("content-type") is not None
    assert len(r2.content) > 0

    # delete
    r3 = client.delete("/settings/profile/logo", headers=headers)
    assert r3.status_code == 204

    # after delete, get should 404
    r4 = client.get("/settings/profile/logo", headers=headers)
    assert r4.status_code == 404


def test_profile_rejects_logo_asset_from_another_tenant(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings_routes, "TENANT_ASSETS_ROOT", tmp_path / "tenant_assets")
    client = TestClient(app)
    first_code = f"logo-owner-{uuid4().hex[:8]}"
    second_code = f"logo-other-{uuid4().hex[:8]}"
    for code in (first_code, second_code):
        response = client.post("/tenants", json={"code": code, "name": code})
        assert response.status_code == 201, response.text

    first_headers = {"X-Tenant-Code": first_code}
    second_headers = {"X-Tenant-Code": second_code}
    upload = client.post(
        "/settings/profile/logo",
        headers=first_headers,
        files={"file": ("logo.png", MIN_PNG, "image/png")},
    )
    assert upload.status_code == 201, upload.text

    rejected = client.put(
        "/settings/profile",
        headers=second_headers,
        json={
            "business_name": "Other SP",
            "logo_asset_id": upload.json()["logo_asset_id"],
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "Invalid logo asset"

    other_profile = client.get("/settings/profile", headers=second_headers)
    assert other_profile.status_code == 200
    assert other_profile.json()["logo_asset_id"] is None
    assert client.get("/settings/profile/logo", headers=first_headers).status_code == 200
