# /home/miso/dev/sp-app/sp-app/backend/tests/test_settings_logo.py
import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


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
    monkeypatch.setenv("TENANT_ASSETS_DIR", str(tmp_path / "tenant_assets"))

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
