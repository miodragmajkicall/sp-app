from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.invoice_profile_helpers import save_complete_profile


client = TestClient(app)


def _headers() -> dict[str, str]:
    headers = {"X-Tenant-Code": f"invoice-buyer-{uuid4().hex[:12]}"}
    save_complete_profile(client, headers)
    return headers


def _payload(invoice_number: str, **buyer_fields) -> dict:
    return {
        "invoice_number": invoice_number,
        "issue_date": "2087-09-01",
        "due_date": "2087-09-08",
        "buyer_name": "Test Buyer",
        "buyer_address": "Test address",
        "items": [
            {
                "description": "Test service",
                "quantity": "1",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
        **buyer_fields,
    }


def test_business_buyer_tax_id_is_stored_returned_and_rendered_in_pdf() -> None:
    headers = _headers()
    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(
            f"BUS-{uuid4().hex[:12]}",
            buyer_type="BUSINESS",
            buyer_name="Primjer d.o.o.",
            buyer_tax_id="4401234560001",
        ),
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["buyer_type"] == "BUSINESS"
    assert created["buyer_name"] == "Primjer d.o.o."
    assert created["buyer_tax_id"] == "4401234560001"

    detail = client.get(f"/invoices/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["buyer_type"] == "BUSINESS"
    assert detail.json()["buyer_tax_id"] == "4401234560001"

    pdf = client.get(f"/invoices/{created['id']}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert b"Primjer d.o.o." in pdf.content
    assert b"JIB/PIB: 4401234560001" in pdf.content


def test_individual_buyer_is_stored_without_tax_id() -> None:
    headers = _headers()
    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(
            f"IND-{uuid4().hex[:12]}",
            buyer_type="INDIVIDUAL",
            buyer_name="Marko Markovic",
            buyer_tax_id=None,
        ),
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["buyer_type"] == "INDIVIDUAL"
    assert created["buyer_name"] == "Marko Markovic"
    assert created["buyer_tax_id"] is None

    pdf = client.get(f"/invoices/{created['id']}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert b"Marko Markovic" in pdf.content
    assert b"JIB/PIB:" not in pdf.content


def test_individual_buyer_with_tax_id_is_rejected() -> None:
    response = client.post(
        "/invoices",
        headers=_headers(),
        json=_payload(
            f"INVALID-{uuid4().hex[:12]}",
            buyer_type="INDIVIDUAL",
            buyer_name="Jovana Jovanovic",
            buyer_tax_id="123456789",
        ),
    )

    assert response.status_code == 422


def test_omitted_buyer_type_remains_legacy_compatible() -> None:
    response = client.post(
        "/invoices",
        headers=_headers(),
        json=_payload(f"LEGACY-{uuid4().hex[:12]}"),
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["buyer_type"] == "UNSPECIFIED"
    assert created["buyer_tax_id"] is None
