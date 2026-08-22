from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import InvoiceAttachment
from app.routes.invoice_attachments import STORAGE_ROOT
from tests.invoice_profile_helpers import save_complete_profile

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
    # Nova kolona treba da postoji u odgovoru (nullable)
    assert "input_invoice_id" in data

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

    - kreiramo izlaznu fakturu za tenanta,
    - uploadujemo attachment za istog tenanta,
    - povežemo attachment sa fakturom (link-to-invoice),
    - listamo sa invoice_id filterom i provjeravamo da je attachment tu
      i da ima postavljen invoice_id i status 'linked_to_invoice'.
    """
    tenant_code = f"att-tenant-link-{int(time.time())}"
    headers = {"X-Tenant-Code": tenant_code}
    save_complete_profile(client, headers)

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
    assert att_data["input_invoice_id"] is None

    # 3) Link attachment -> izlazna faktura
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
    # svi vraćeni attachment-i treba da imaju isti invoice_id
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
            "file": (
                "test-neg.pdf",
                b"%PDF-1.4\nINVOICE LINK NEG TEST",
                "application/pdf",
            ),
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
            "file": (
                "status-test.pdf",
                b"%PDF-1.4\nSTATUS TEST",
                "application/pdf",
            ),
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
            "file": (
                "status-neg.pdf",
                b"%PDF-1.4\nSTATUS NEG TEST",
                "application/pdf",
            ),
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


def test_invoice_attachment_link_to_input_invoice_ok() -> None:
    """
    Tok za ulazne fakture:

    - kreiramo ulaznu fakturu za tenanta,
    - uploadujemo attachment,
    - povežemo attachment sa ulaznom fakturom (link-to-input-invoice),
    - provjeravamo da su input_invoice_id i status ispravno postavljeni.
    """
    tenant_code = f"att-tenant-link-input-{int(time.time())}"
    headers = {"X-Tenant-Code": tenant_code}

    # 1) Kreiramo ulaznu fakturu za ovog tenanta
    input_invoice_payload = {
        "supplier_name": "Dobavljač X",
        "supplier_tax_id": "9876543210000",
        "supplier_address": "Ulica 1, Banja Luka",
        "invoice_number": "INP-001",
        "issue_date": "2025-02-01",
        "due_date": "2025-02-10",
        "total_base": "50.00",
        "total_vat": "8.50",
        "total_amount": "58.50",
        "note": "Test ulazne fakture",
    }
    inp_resp = client.post(
        "/input-invoices",
        json=input_invoice_payload,
        headers=headers,
    )
    assert inp_resp.status_code == 201, inp_resp.text
    input_invoice = inp_resp.json()
    input_invoice_id = input_invoice["id"]
    assert isinstance(input_invoice_id, int)

    # 2) Upload attachment za istog tenanta
    filename = "ulazna-faktura-input-link.pdf"
    content = b"%PDF-1.4\nINPUT LINK TEST"
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
    assert att_data["input_invoice_id"] is None

    # 3) Link attachment -> ulazna faktura
    link_resp = client.post(
        f"/invoice-attachments/{attachment_id}/link-to-input-invoice",
        headers=headers,
        json={"input_invoice_id": input_invoice_id},
    )
    assert link_resp.status_code == 200, link_resp.text
    linked = link_resp.json()
    assert linked["id"] == attachment_id
    assert linked["tenant_code"] == tenant_code
    assert linked["input_invoice_id"] == input_invoice_id
    # korisitmo status 'matched_to_invoice' za uspješno uparenu ulaznu fakturu
    assert linked["status"] == "matched_to_invoice"


def test_invoice_attachment_link_to_input_invoice_fails_for_wrong_input_invoice() -> None:
    """
    Negativni scenario za ulazne fakture:

    - uploadujemo attachment za tenanta,
    - pokušamo da ga povežemo sa input_invoice_id koji ne postoji
      ili ne pripada tom tenantu -> očekujemo 404 'Input invoice not found'.
    """
    tenant_code = "att-tenant-link-input-neg"
    headers = {"X-Tenant-Code": tenant_code}

    # Upload attachment
    upload_resp = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "input-neg.pdf",
                b"%PDF-1.4\nINPUT NEG TEST",
                "application/pdf",
            ),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    att_data = upload_resp.json()
    attachment_id = att_data["id"]
    assert isinstance(attachment_id, int)

    # Pokušaj linkovanja na nepostojeći input_invoice_id
    link_resp = client.post(
        f"/invoice-attachments/{attachment_id}/link-to-input-invoice",
        headers=headers,
        json={"input_invoice_id": 999999},
    )
    assert link_resp.status_code == 404
    body = link_resp.json()
    assert body.get("detail") == "Input invoice not found"


def test_invoice_attachment_rejects_fake_pdf_content() -> None:
    tenant_code = "att-security-fake-pdf"
    headers = {"X-Tenant-Code": tenant_code}

    response = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "fake-invoice.pdf",
                b"This is plain text, not a PDF file.",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 415, response.text
    assert response.json() == {
        "detail": "Unsupported attachment type; only PDF, JPEG, and PNG are allowed"
    }


def test_invoice_attachment_detects_jpeg_from_content() -> None:
    tenant_code = "att-security-jpeg"
    headers = {"X-Tenant-Code": tenant_code}
    filename = "receipt-upload.bin"
    content = b"\xff\xd8\xff\xe0JPEG TEST CONTENT"

    response = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                filename,
                content,
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["filename"] == filename
    assert data["content_type"] == "image/jpeg"
    assert data["size_bytes"] == len(content)
    assert data["storage_path"].endswith(".jpg")
    assert filename not in data["storage_path"]
    assert tenant_code not in data["storage_path"]


def test_invoice_attachment_detects_png_from_content() -> None:
    tenant_code = "att-security-png"
    headers = {"X-Tenant-Code": tenant_code}
    filename = "receipt-upload.dat"
    content = b"\x89PNG\r\n\x1a\nPNG TEST CONTENT"

    response = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                filename,
                content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["filename"] == filename
    assert data["content_type"] == "image/png"
    assert data["size_bytes"] == len(content)
    assert data["storage_path"].endswith(".png")
    assert filename not in data["storage_path"]
    assert tenant_code not in data["storage_path"]


def test_invoice_attachment_rejects_file_larger_than_10_mib() -> None:
    tenant_code = "att-security-too-large"
    headers = {"X-Tenant-Code": tenant_code}

    content = b"%PDF-1.4\n" + (b"A" * (10 * 1024 * 1024))

    response = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "too-large.pdf",
                content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 413, response.text
    assert response.json() == {
        "detail": "Attachment exceeds maximum size of 10 MiB"
    }


def test_invoice_attachment_download_blocks_storage_path_traversal() -> None:
    tenant_code = "att-security-download-traversal"
    headers = {"X-Tenant-Code": tenant_code}
    content = b"%PDF-1.4\nTRAVERSAL DOWNLOAD TEST"

    upload_response = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "download-traversal.pdf",
                content,
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201, upload_response.text

    attachment_id = upload_response.json()["id"]
    original_storage_path = upload_response.json()["storage_path"]

    outside_path = STORAGE_ROOT.resolve().parent / (
        f"attachment-download-traversal-{attachment_id}.pdf"
    )
    outside_path.write_bytes(b"OUTSIDE STORAGE SECRET")

    try:
        with SessionLocal() as db:
            attachment = db.get(InvoiceAttachment, attachment_id)
            assert attachment is not None
            attachment.storage_path = f"../{outside_path.name}"
            db.commit()

        response = client.get(
            f"/invoice-attachments/{attachment_id}/download",
            headers=headers,
        )

        assert response.status_code == 404, response.text
        assert response.json() == {"detail": "File not found"}
        assert outside_path.is_file()
        assert outside_path.read_bytes() == b"OUTSIDE STORAGE SECRET"
    finally:
        with SessionLocal() as db:
            attachment = db.get(InvoiceAttachment, attachment_id)
            if attachment is not None:
                attachment.storage_path = original_storage_path
                db.commit()

        client.delete(
            f"/invoice-attachments/{attachment_id}",
            headers=headers,
        )

        if outside_path.exists():
            outside_path.unlink()


def test_invoice_attachment_delete_blocks_storage_path_traversal() -> None:
    tenant_code = "att-security-delete-traversal"
    headers = {"X-Tenant-Code": tenant_code}
    content = b"%PDF-1.4\nTRAVERSAL DELETE TEST"

    upload_response = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "delete-traversal.pdf",
                content,
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201, upload_response.text

    attachment_id = upload_response.json()["id"]
    original_storage_path = upload_response.json()["storage_path"]

    outside_path = STORAGE_ROOT.resolve().parent / (
        f"attachment-delete-traversal-{attachment_id}.pdf"
    )
    outside_path.write_bytes(b"DO NOT DELETE")

    try:
        with SessionLocal() as db:
            attachment = db.get(InvoiceAttachment, attachment_id)
            assert attachment is not None
            attachment.storage_path = f"../{outside_path.name}"
            db.commit()

        response = client.delete(
            f"/invoice-attachments/{attachment_id}",
            headers=headers,
        )

        assert response.status_code == 404, response.text
        assert response.json() == {"detail": "File not found"}
        assert outside_path.is_file()
        assert outside_path.read_bytes() == b"DO NOT DELETE"

        with SessionLocal() as db:
            attachment = db.get(InvoiceAttachment, attachment_id)
            assert attachment is not None
            assert attachment.storage_path == f"../{outside_path.name}"
    finally:
        with SessionLocal() as db:
            attachment = db.get(InvoiceAttachment, attachment_id)
            if attachment is not None:
                attachment.storage_path = original_storage_path
                db.commit()

        client.delete(
            f"/invoice-attachments/{attachment_id}",
            headers=headers,
        )

        if outside_path.exists():
            outside_path.unlink()


def test_invoice_attachment_filters_by_input_invoice_id() -> None:
    tenant_code = f"att-filter-input-{time.time_ns()}"
    headers = {"X-Tenant-Code": tenant_code}

    input_invoice_response = client.post(
        "/input-invoices",
        headers=headers,
        json={
            "supplier_name": "Filter Dobavljač",
            "invoice_number": "FILTER-001",
            "issue_date": "2026-08-20",
            "due_date": "2026-08-25",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert input_invoice_response.status_code == 201, input_invoice_response.text
    input_invoice_id = input_invoice_response.json()["id"]

    linked_upload = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "linked-input.pdf",
                b"%PDF-1.4\nLINKED INPUT FILTER TEST",
                "application/pdf",
            ),
        },
    )
    assert linked_upload.status_code == 201, linked_upload.text
    linked_attachment_id = linked_upload.json()["id"]

    unrelated_upload = client.post(
        "/invoice-attachments",
        headers=headers,
        files={
            "file": (
                "unrelated-input.pdf",
                b"%PDF-1.4\nUNRELATED INPUT FILTER TEST",
                "application/pdf",
            ),
        },
    )
    assert unrelated_upload.status_code == 201, unrelated_upload.text
    unrelated_attachment_id = unrelated_upload.json()["id"]

    link_response = client.post(
        f"/invoice-attachments/{linked_attachment_id}/link-to-input-invoice",
        headers=headers,
        json={"input_invoice_id": input_invoice_id},
    )
    assert link_response.status_code == 200, link_response.text

    list_response = client.get(
        "/invoice-attachments",
        headers=headers,
        params={"input_invoice_id": input_invoice_id},
    )
    assert list_response.status_code == 200, list_response.text

    items = list_response.json()
    ids = [item["id"] for item in items]

    assert linked_attachment_id in ids
    assert unrelated_attachment_id not in ids
    assert all(
        item["input_invoice_id"] == input_invoice_id
        for item in items
    )

    client.delete(
        f"/invoice-attachments/{linked_attachment_id}",
        headers=headers,
    )
    client.delete(
        f"/invoice-attachments/{unrelated_attachment_id}",
        headers=headers,
    )


def test_invoice_attachment_download_is_tenant_isolated() -> None:
    owner_tenant = f"att-download-owner-{time.time_ns()}"
    other_tenant = f"att-download-other-{time.time_ns()}"
    owner_headers = {"X-Tenant-Code": owner_tenant}
    other_headers = {"X-Tenant-Code": other_tenant}

    upload_response = client.post(
        "/invoice-attachments",
        headers=owner_headers,
        files={
            "file": (
                "tenant-download.pdf",
                b"%PDF-1.4\nTENANT DOWNLOAD TEST",
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201, upload_response.text
    attachment_id = upload_response.json()["id"]

    response = client.get(
        f"/invoice-attachments/{attachment_id}/download",
        headers=other_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Attachment not found"}

    owner_response = client.get(
        f"/invoice-attachments/{attachment_id}/download",
        headers=owner_headers,
    )
    assert owner_response.status_code == 200, owner_response.text

    delete_response = client.delete(
        f"/invoice-attachments/{attachment_id}",
        headers=owner_headers,
    )
    assert delete_response.status_code == 204, delete_response.text


def test_invoice_attachment_delete_is_tenant_isolated() -> None:
    owner_tenant = f"att-delete-owner-{time.time_ns()}"
    other_tenant = f"att-delete-other-{time.time_ns()}"
    owner_headers = {"X-Tenant-Code": owner_tenant}
    other_headers = {"X-Tenant-Code": other_tenant}

    upload_response = client.post(
        "/invoice-attachments",
        headers=owner_headers,
        files={
            "file": (
                "tenant-delete.pdf",
                b"%PDF-1.4\nTENANT DELETE TEST",
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201, upload_response.text
    attachment_id = upload_response.json()["id"]

    response = client.delete(
        f"/invoice-attachments/{attachment_id}",
        headers=other_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Attachment not found"}

    owner_download = client.get(
        f"/invoice-attachments/{attachment_id}/download",
        headers=owner_headers,
    )
    assert owner_download.status_code == 200, owner_download.text

    owner_delete = client.delete(
        f"/invoice-attachments/{attachment_id}",
        headers=owner_headers,
    )
    assert owner_delete.status_code == 204, owner_delete.text


def test_invoice_attachment_input_invoice_link_is_tenant_isolated() -> None:
    owner_tenant = f"att-link-owner-{time.time_ns()}"
    other_tenant = f"att-link-other-{time.time_ns()}"
    owner_headers = {"X-Tenant-Code": owner_tenant}
    other_headers = {"X-Tenant-Code": other_tenant}

    upload_response = client.post(
        "/invoice-attachments",
        headers=owner_headers,
        files={
            "file": (
                "tenant-link.pdf",
                b"%PDF-1.4\nTENANT LINK TEST",
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201, upload_response.text
    attachment_id = upload_response.json()["id"]

    foreign_invoice_response = client.post(
        "/input-invoices",
        headers=other_headers,
        json={
            "supplier_name": "Foreign Dobavljač",
            "invoice_number": "FOREIGN-001",
            "issue_date": "2026-08-20",
            "due_date": "2026-08-25",
            "total_base": "100.00",
            "total_vat": "17.00",
            "total_amount": "117.00",
        },
    )
    assert (
        foreign_invoice_response.status_code == 201
    ), foreign_invoice_response.text
    foreign_input_invoice_id = foreign_invoice_response.json()["id"]

    # Drugi tenant ne smije ni pristupiti attachment-u vlasnika.
    response_as_other_tenant = client.post(
        f"/invoice-attachments/{attachment_id}/link-to-input-invoice",
        headers=other_headers,
        json={"input_invoice_id": foreign_input_invoice_id},
    )

    assert response_as_other_tenant.status_code == 404
    assert response_as_other_tenant.json() == {
        "detail": "Attachment not found"
    }

    # Ni vlasnik attachment-a ne smije linkovati fakturu drugog tenanta.
    response_as_owner = client.post(
        f"/invoice-attachments/{attachment_id}/link-to-input-invoice",
        headers=owner_headers,
        json={"input_invoice_id": foreign_input_invoice_id},
    )

    assert response_as_owner.status_code == 404
    assert response_as_owner.json() == {
        "detail": "Input invoice not found"
    }

    delete_response = client.delete(
        f"/invoice-attachments/{attachment_id}",
        headers=owner_headers,
    )
    assert delete_response.status_code == 204, delete_response.text
