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


def test_invoice_attachment_delete_flow() -> None:
    """
    CRUD tok za attachment:

    - uploadujemo fajl za konkretnog tenanta,
    - provjeravamo da je u listi,
    - brišemo ga preko DELETE /invoice-attachments/{id},
    - ponovo listamo i provjeravamo da više nije u listi.
    """
    tenant_code = "att-tenant-delete"
    filename = "ulazna-faktura-delete.pdf"
    content = b"%PDF-1.4\nDELETE TEST"

    # 1) Upload
    upload_resp = client.post(
        "/invoice-attachments",
        headers={"X-Tenant-Code": tenant_code},
        files={
            "file": (filename, content, "application/pdf"),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    data = upload_resp.json()
    attachment_id = data["id"]
    assert isinstance(attachment_id, int)

    # 2) List prije brisanja -> attachment mora postojati
    list_before = client.get(
        "/invoice-attachments",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert list_before.status_code == 200
    items_before = list_before.json()
    ids_before = [item["id"] for item in items_before]
    assert attachment_id in ids_before

    # 3) DELETE
    delete_resp = client.delete(
        f"/invoice-attachments/{attachment_id}",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert delete_resp.status_code == 204, delete_resp.text

    # 4) List nakon brisanja -> attachment više ne smije biti u listi
    list_after = client.get(
        "/invoice-attachments",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert list_after.status_code == 200
    items_after = list_after.json()
    ids_after = [item["id"] for item in items_after]
    assert attachment_id not in ids_after
