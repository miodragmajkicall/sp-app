from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.db import get_session as _get_session_dep
from app.models import Invoice

client = TestClient(app)


@contextmanager
def _db_session_for_test():
    """
    Helper context manager za direktan rad sa DB u testovima.

    Koristimo isti get_session dependency kao i API, ali ga ovdje
    ručno "vozimо" kao generator:
    - next() -> Session
    - drugi next() će pokrenuti finally blok i zatvoriti sesiju.
    """
    gen = _get_session_dep()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _make_invoice_payload(
    invoice_number: str,
    buyer_name: str = "PDF Test Buyer",
) -> dict:
    """
    Helper za kreiranje minimalno validnog payload-a za fakturu.
    """
    return {
        "invoice_number": invoice_number,
        "issue_date": date(2088, 1, 15).isoformat(),
        "due_date": date(2088, 2, 15).isoformat(),
        "buyer_name": buyer_name,
        "buyer_address": "Test ulica 1, Banja Luka",
        "items": [
            {
                "description": "Test stavka 1",
                "quantity": "2",
                "unit_price": "10.00",
                "vat_rate": "0.17",
            },
            {
                "description": "Test stavka 2",
                "quantity": "1",
                "unit_price": "5.00",
                "vat_rate": "0.17",
            },
        ],
    }


def test_invoice_pdf_generation_happy_path() -> None:
    """
    Happy-path test za PDF generisanje fakture:

    - kreiramo fakturu za tenanta 'pdf-tenant-a',
    - pozivamo GET /invoices/{id}/pdf,
    - očekujemo:
        * 200 OK,
        * Content-Type: application/pdf,
        * Content-Disposition sa 'inline' i ispravnim imenom fajla,
        * PDF sadržaj počinje sa '%PDF-1.4' i sadrži osnovni tekst fakture.
    """
    tenant_code = "pdf-tenant-a"
    invoice_number = "PDF-INV-001"

    # 0) Očistimo potencijalne stare fakture sa istim brojem za ovog tenanta
    with _db_session_for_test() as db:
        db.query(Invoice).filter(
            Invoice.tenant_code == tenant_code,
            Invoice.invoice_number == invoice_number,
        ).delete()
        db.commit()

    # 1) Kreiramo fakturu
    create_resp = client.post(
        "/invoices",
        headers={"X-Tenant-Code": tenant_code},
        json=_make_invoice_payload(invoice_number),
    )
    assert create_resp.status_code == 201, create_resp.text

    invoice_data = create_resp.json()
    invoice_id = invoice_data["id"]
    assert invoice_data["invoice_number"] == invoice_number

    # 2) Preuzimamo PDF
    pdf_resp = client.get(
        f"/invoices/{invoice_id}/pdf",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert pdf_resp.status_code == 200

    # Headeri
    ct = pdf_resp.headers.get("content-type", "")
    assert ct.startswith("application/pdf")

    cd = pdf_resp.headers.get("content-disposition", "")
    assert "inline" in cd
    assert f"invoice-{invoice_number}" in cd

    # Sadržaj PDF-a
    content = pdf_resp.content
    assert content.startswith(b"%PDF-1.4")
    # Provjerimo da se unutar PDF-a nalaze osnovni podaci iz fakture
    assert b"Faktura br:" in content
    assert invoice_number.encode("ascii") in content
    assert tenant_code.encode("ascii") in content
    assert b"Osnovica:" in content
    assert b"Ukupno:" in content


def test_invoice_pdf_not_accessible_for_other_tenant() -> None:
    """
    Sigurnosni test: faktura se ne smije moći preuzeti kao PDF
    sa drugim X-Tenant-Code header-om.

    - kreiramo fakturu za tenanta 'pdf-tenant-b',
    - pokušamo da preuzmemo PDF sa header-om drugog tenanta,
    - očekujemo 404 (Invoice not found).
    """
    tenant_owner = "pdf-tenant-b"
    other_tenant = "pdf-tenant-c"
    invoice_number = "PDF-INV-002"

    # 0) Očistimo potencijalne stare fakture sa istim brojem za tenant_owner
    with _db_session_for_test() as db:
        db.query(Invoice).filter(
            Invoice.tenant_code == tenant_owner,
            Invoice.invoice_number == invoice_number,
        ).delete()
        db.commit()

    # 1) Kreiramo fakturu za tenant_owner
    create_resp = client.post(
        "/invoices",
        headers={"X-Tenant-Code": tenant_owner},
        json=_make_invoice_payload(invoice_number, buyer_name="PDF Buyer 2"),
    )
    assert create_resp.status_code == 201, create_resp.text

    invoice_data = create_resp.json()
    invoice_id = invoice_data["id"]

    # 2) Pokušavamo preuzeti PDF sa drugim tenant header-om
    pdf_resp = client.get(
        f"/invoices/{invoice_id}/pdf",
        headers={"X-Tenant-Code": other_tenant},
    )
    assert pdf_resp.status_code == 404
    body = pdf_resp.json()
    assert body.get("detail") == "Invoice not found"
