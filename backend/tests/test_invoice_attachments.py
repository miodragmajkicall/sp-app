from __future__ import annotations

import time

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


def test_invoice_attachment_download_flow() -> None:
    """
    Download tok za attachment:

    - uploadujemo fajl za konkretnog tenanta,
    - pozivamo GET /invoice-attachments/{id}/download,
    - provjeravamo status, Content-Type, Content-Disposition i sadržaj fajla.
    """
    tenant_code = "att-tenant-download"
    filename = "ulazna-faktura-download.pdf"
    content = b"%PDF-1.4\nDOWNLOAD TEST"

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

    # 2) Download
    download_resp = client.get(
        f"/invoice-attachments/{attachment_id}/download",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert download_resp.status_code == 200, download_resp.text
    # Content-Type
    assert download_resp.headers["content-type"].startswith("application/pdf")
    # Content-Disposition treba da sadrži filename
    content_disp = download_resp.headers.get("content-disposition", "")
    assert "filename=" in content_disp
    assert filename in content_disp
    # Sadržaj fajla
    assert download_resp.content == content


def test_invoice_attachment_link_to_invoice_and_filter_by_invoice() -> None:
    """
    Tok:

    - kreiramo fakturu za tenanta,
    - uploadujemo attachment za istog tenanta,
    - povežemo attachment sa fakturom (link-to-invoice),
    - listamo sa invoice_id filterom i provjeravamo da je attachment tu
      i da ima postavljen invoice_id i status 'linked_to_invoice'.
    """
    tenant_code = f"att-tenant-link-{int(time.time())}"
    headers = {"X-Tenant-Code": tenant_code}

    # 1) Kreiramo fakturu za ovog tenanta
    invoice_payload = {
        "invoice_number": "LINK-001",
        "issue_date": "2025-01-10",
        "due_date": "2025-01-20",
        "buyer_name": "Link Buyer d.o.o.",
        "buyer_address": "Banja Luka",
        "items": [
            {
                "description": "Usluga X",
                "quantity": "1.00",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
    }
    inv_resp = client.post("/invoices/", json=invoice_payload, headers=headers)
    assert inv_resp.status_code == 201, inv_resp.text
    invoice_data = inv_resp.json()
    invoice_id = invoice_data["id"]
    assert isinstance(invoice_id, int)

    # 2) Upload attachment za istog tenanta
    filename = "ulazna-faktura-link.pdf"
    content = b"%PDF-1.4\nLINK TEST"
    upload_resp = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (filename, content, "application/pdf"),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    att_data = upload_resp.json()
    attachment_id = att_data["id"]
    assert isinstance(attachment_id, int)
    assert att_data["invoice_id"] is None

    # 3) Link attachment -> invoice
    link_resp = client.post(
        f"/invoice-attachments/{attachment_id}/link-to-invoice",
        headers=headers,
        json={"invoice_id": invoice_id},
    )
    assert link_resp.status_code == 200, link_resp.text
    linked = link_resp.json()
    assert linked["id"] == attachment_id
    assert linked["tenant_code"] == tenant_code
    assert linked["invoice_id"] == invoice_id
    assert linked["status"] == "linked_to_invoice"

    # 4) List sa invoice_id filterom
    list_resp = client.get(
        "/invoice-attachments",
        headers=headers,
        params={"invoice_id": invoice_id},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    ids = [item["id"] for item in items]
    assert attachment_id in ids
    # svi vratjeni attachment-i treba da imaju isti invoice_id
    for item in items:
        assert item["invoice_id"] == invoice_id


def test_invoice_attachment_link_to_invoice_fails_for_wrong_invoice() -> None:
    """
    Negativni scenario:

    - uploadujemo attachment za jednog tenanta,
    - pokušamo da ga povežemo sa invoice_id koji ne postoji
      ili ne pripada tom tenantu -> očekujemo 404 'Invoice not found'.
    """
    tenant_code = "att-tenant-link-neg"
    headers = {"X-Tenant-Code": tenant_code}

    # Upload attachment
    upload_resp = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": ("test-neg.pdf", b"NEG", "application/pdf"),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    att_data = upload_resp.json()
    attachment_id = att_data["id"]
    assert isinstance(attachment_id, int)

    # Pokušaj linkovanja na nepostojeći invoice_id
    link_resp = client.post(
        f"/invoice-attachments/{attachment_id}/link-to-invoice",
        headers=headers,
        json={"invoice_id": 999999},
    )
    assert link_resp.status_code == 404
    body = link_resp.json()
    assert body.get("detail") == "Invoice not found"


def test_invoice_attachment_status_update_flow() -> None:
    """
    OCR skeleton flow:

    - uploadujemo attachment za tenanta,
    - status po defaultu treba da bude 'uploaded',
    - postavljamo status na 'ocr_pending',
    - zatim na 'ocr_done',
    - provjeravamo da se statusi pravilno ažuriraju.
    """
    tenant_code = "att-tenant-status"
    headers = {"X-Tenant-Code": tenant_code}

    # 1) Upload
    upload_resp = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": ("status-test.pdf", b"STATUS", "application/pdf"),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    data = upload_resp.json()
    attachment_id = data["id"]
    assert isinstance(attachment_id, int)
    assert data["status"] == "uploaded"

    # 2) Status -> ocr_pending
    pending_resp = client.post(
        f"/invoice-attachments/{attachment_id}/status",
        headers=headers,
        json={"status": "ocr_pending"},
    )
    assert pending_resp.status_code == 200, pending_resp.text
    pending = pending_resp.json()
    assert pending["id"] == attachment_id
    assert pending["status"] == "ocr_pending"

    # 3) Status -> ocr_done
    done_resp = client.post(
        f"/invoice-attachments/{attachment_id}/status",
        headers=headers,
        json={"status": "ocr_done"},
    )
    assert done_resp.status_code == 200, done_resp.text
    done = done_resp.json()
    assert done["id"] == attachment_id
    assert done["status"] == "ocr_done"


def test_invoice_attachment_status_invalid_value() -> None:
    """
    Negativni scenario:

    - uploadujemo attachment za tenanta,
    - pokušamo da postavimo status na nedozvoljenu vrijednost,
    - očekujemo 400 + 'Invalid status value'.
    """
    tenant_code = "att-tenant-status-neg"
    headers = {"X-Tenant-Code": tenant_code}

    upload_resp = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": ("status-neg.pdf", b"NEG", "application/pdf"),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    data = upload_resp.json()
    attachment_id = data["id"]
    assert isinstance(attachment_id, int)

    bad_resp = client.post(
        f"/invoice-attachments/{attachment_id}/status",
        headers=headers,
        json={"status": "not-a-valid-status"},
    )
    assert bad_resp.status_code == 400
    body = bad_resp.json()
    assert body.get("detail") == "Invalid status value"
