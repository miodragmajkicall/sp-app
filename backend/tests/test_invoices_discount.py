from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.invoices import _calculate_invoice_item_amounts
from tests.invoice_profile_helpers import save_complete_profile


client = TestClient(app)


def _payload(invoice_number: str, items: list[dict]) -> dict:
    return {
        "invoice_number": invoice_number,
        "issue_date": "2087-08-12",
        "due_date": "2087-08-19",
        "buyer_name": "Discount Test Buyer",
        "items": items,
    }


def _headers() -> dict[str, str]:
    headers = {"X-Tenant-Code": f"invoice-discount-{uuid4().hex[:12]}"}
    save_complete_profile(client, headers)
    return headers


def test_discount_calculation_uses_round_half_up_per_line() -> None:
    assert _calculate_invoice_item_amounts(
        quantity=Decimal("1"),
        unit_price=Decimal("10.05"),
        discount_percent=Decimal("50"),
        vat_rate=Decimal("0.17"),
    ) == (Decimal("5.03"), Decimal("0.86"), Decimal("5.89"))

    assert _calculate_invoice_item_amounts(
        quantity=Decimal("1"),
        unit_price=Decimal("0.15"),
        discount_percent=Decimal("50"),
        vat_rate=Decimal("0.17"),
    ) == (Decimal("0.08"), Decimal("0.01"), Decimal("0.09"))


def test_create_and_get_invoice_return_discounted_authoritative_totals() -> None:
    headers = _headers()
    payload = _payload(
        f"DISC-{uuid4().hex[:12]}",
        [
            {
                "description": "Rounded discounted item",
                "quantity": "1",
                "unit_price": "10.05",
                "discount_percent": "50.00",
                "vat_rate": "0.17",
            },
            {
                "description": "Second discounted item",
                "quantity": "2",
                "unit_price": "3.33",
                "discount_percent": "10.00",
                "vat_rate": "0.17",
            },
        ],
    )

    created_response = client.post("/invoices", headers=headers, json=payload)
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()

    assert created["total_base"] == "11.02"
    assert created["total_vat"] == "1.88"
    assert created["total_amount"] == "12.90"
    assert created["items"][0]["discount_percent"] == "50.00"
    assert created["items"][0]["base_amount"] == "5.03"
    assert created["items"][0]["vat_amount"] == "0.86"
    assert created["items"][0]["total_amount"] == "5.89"
    assert created["items"][1]["discount_percent"] == "10.00"
    assert created["items"][1]["base_amount"] == "5.99"
    assert created["items"][1]["vat_amount"] == "1.02"
    assert created["items"][1]["total_amount"] == "7.01"

    detail_response = client.get(
        f"/invoices/{created['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json() == created

    pdf_response = client.get(
        f"/invoices/{created['id']}/pdf",
        headers=headers,
    )
    assert pdf_response.status_code == 200
    assert b"50.00%" in pdf_response.content
    assert b"Ukupno: 12.90 KM" in pdf_response.content


def test_discount_defaults_to_zero_for_existing_clients() -> None:
    response = client.post(
        "/invoices",
        headers=_headers(),
        json=_payload(
            f"DEFAULT-{uuid4().hex[:12]}",
            [
                {
                    "description": "No explicit discount",
                    "quantity": "1",
                    "unit_price": "10.00",
                    "vat_rate": "0.17",
                }
            ],
        ),
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["items"][0]["discount_percent"] == "0.00"
    assert created["total_base"] == "10.00"
    assert created["total_vat"] == "1.70"
    assert created["total_amount"] == "11.70"


@pytest.mark.parametrize("discount_percent", ["-0.01", "100.00", "101.00"])
def test_discount_outside_safe_range_is_rejected(discount_percent: str) -> None:
    response = client.post(
        "/invoices",
        headers=_headers(),
        json=_payload(
            f"INVALID-{uuid4().hex[:12]}",
            [
                {
                    "description": "Invalid discount",
                    "quantity": "1",
                    "unit_price": "10.00",
                    "discount_percent": discount_percent,
                    "vat_rate": "0.17",
                }
            ],
        ),
    )

    assert response.status_code == 422
