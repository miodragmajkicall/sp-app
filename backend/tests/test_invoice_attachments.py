from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_invoice_attachment_upload_and_list_happy_path() -> None:
    """
    Happy-path test za upload i listanje attachment-a ulaznih faktura:

    - uploadujemo jedan PDF za tenanta 'att-tenant-a',
    - očekujemo 201 i korektne metapodatke,
    - pozivamo GET /invoice-attachments za istog tenanta,
    - provjeravamo da je naš fajl u listi.
    """
    tenant_code = "att-tenant-a"
    filename = "ulazna-faktura-001.pdf"
    content = b"%PDF-1.4\nTEST FAKTURA"

    # 1) Upload
    resp = client.post(
        "/invoice-attachments",
        headers={"X-Tenant-Code": tenant_code},
        files={
            "file": (filename, content, "application/pdf"),
        },
    )
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert isinstance(data["id"], int)
    assert data["tenant_code"] == tenant_code
    assert data["filename"] == filename
    assert data["content_type"].startswith("application/pdf")
    assert data["size_bytes"] == len(content)
    assert data["status"] == "uploaded"
    assert "created_at" in data

    # 2) List za istog tenanta
    list_resp = client.get(
        "/invoice-attachments",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    # Provjerimo da je naš fajl u rezultatu (po filename-u)
    filenames = [item["filename"] for item in items]
    assert filename in filenames


def test_invoice_attachment_requires_tenant_and_file() -> None:
    """
    Negativni testovi:

    - bez X-Tenant-Code header-a → 400 (Missing X-Tenant-Code),
    - bez fajla → 422 (validation error) jer je 'file' obavezan field.
    """

    # 1) Bez X-Tenant-Code header-a
    resp_no_tenant = client.post(
        "/invoice-attachments",
        files={"file": ("test.pdf", b"data", "application/pdf")},
    )
    assert resp_no_tenant.status_code == 400
    body = resp_no_tenant.json()
    assert body.get("detail") == "Missing X-Tenant-Code header"

    # 2) Bez fajla, ali sa tenant-om -> očekujemo 422 (validation error)
    resp_no_file = client.post(
        "/invoice-attachments",
        headers={"X-Tenant-Code": "att-tenant-b"},
    )
    assert resp_no_file.status_code == 422
