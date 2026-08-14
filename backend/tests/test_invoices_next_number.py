from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.invoice_profile_helpers import save_complete_profile


client = TestClient(app)


def _headers(prefix: str = "next-number") -> dict[str, str]:
    headers = {"X-Tenant-Code": f"nn-{uuid4().hex[:12]}-{prefix}"}
    save_complete_profile(client, headers)
    return headers


def _payload(invoice_number: str, issue_date: str = "2026-08-10") -> dict:
    return {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "due_date": issue_date,
        "buyer_type": "BUSINESS",
        "buyer_name": "Next Number Buyer",
        "buyer_address": "Test address",
        "buyer_tax_id": "4401234560001",
        "items": [
            {
                "description": "Test service",
                "quantity": "1",
                "unit_price": "100.00",
                "discount_percent": "0.00",
                "vat_rate": "0.17",
            }
        ],
    }


def _create_invoice(
    headers: dict[str, str],
    invoice_number: str,
    issue_date: str = "2026-08-10",
) -> None:
    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(invoice_number, issue_date),
    )
    assert response.status_code == 201, response.text


def _next_number(headers: dict[str, str], issue_date: str) -> str:
    response = client.get(
        "/invoices/next-number",
        headers=headers,
        params={"issue_date": issue_date},
    )
    assert response.status_code == 200, response.text
    return response.json()["invoice_number"]


def test_next_number_starts_at_0001_and_does_not_create_invoice() -> None:
    headers = _headers("empty")

    before = client.get("/invoices/list", headers=headers)
    suggested = _next_number(headers, "2026-08-10")
    after = client.get("/invoices/list", headers=headers)

    assert before.status_code == 200, before.text
    assert after.status_code == 200, after.text
    assert before.json()["total"] == 0
    assert suggested == "2026/08/0001"
    assert after.json()["total"] == 0


def test_next_number_uses_highest_numeric_suffix_and_fills_gap() -> None:
    headers = _headers("gap")
    for suffix in ("0001", "0002", "0004"):
        _create_invoice(headers, f"2026/08/{suffix}")

    assert _next_number(headers, "2026-08-10") == "2026/08/0005"


def test_next_number_considers_rows_beyond_default_list_page() -> None:
    headers = _headers("pagination")
    _create_invoice(headers, "2026/08/0099")
    for suffix in range(1, 26):
        _create_invoice(headers, f"2026/08/{suffix:04d}")

    first_page = client.get("/invoices/list", headers=headers)

    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["total"] == 26
    assert len(first_page.json()["items"]) == 20
    assert all(
        item["invoice_number"] != "2026/08/0099"
        for item in first_page.json()["items"]
    )
    assert _next_number(headers, "2026-08-10") == "2026/08/0100"


def test_next_number_is_tenant_scoped() -> None:
    target_headers = _headers("tenant-target")
    other_headers = _headers("tenant-other")
    _create_invoice(other_headers, "2026/08/0042")

    assert _next_number(target_headers, "2026-08-10") == "2026/08/0001"
    assert _next_number(other_headers, "2026-08-10") == "2026/08/0043"


def test_next_number_is_scoped_to_issue_year_and_month() -> None:
    headers = _headers("period")
    _create_invoice(headers, "2026/07/0040", "2026-07-10")
    _create_invoice(headers, "2025/08/0050", "2025-08-10")
    _create_invoice(headers, "2026/08/0003", "2026-08-10")

    assert _next_number(headers, "2026-08-25") == "2026/08/0004"
    assert _next_number(headers, "2026-07-25") == "2026/07/0041"
    assert _next_number(headers, "2025-08-25") == "2025/08/0051"


def test_next_number_ignores_custom_and_non_numeric_suffixes() -> None:
    headers = _headers("formats")
    for invoice_number in (
        "2026/08/0004",
        "2026/08/",
        "2026/08/0009-extra",
        "2026/08/ABCD",
        "2026/08/12A3",
        "CUSTOM-2026/08/0099",
    ):
        _create_invoice(headers, invoice_number)

    assert _next_number(headers, "2026-08-10") == "2026/08/0005"


def test_next_number_keeps_at_least_four_digits() -> None:
    headers = _headers("padding")
    _create_invoice(headers, "2026/08/0009")

    assert _next_number(headers, "2026-08-10") == "2026/08/0010"


def test_next_number_continues_above_9999_without_truncation() -> None:
    headers = _headers("large")
    _create_invoice(headers, "2026/08/10000")

    assert _next_number(headers, "2026-08-10") == "2026/08/10001"


def test_next_number_requires_tenant_header() -> None:
    response = client.get(
        "/invoices/next-number",
        params={"issue_date": "2026-08-10"},
    )

    assert response.status_code == 400


def test_next_number_requires_valid_issue_date() -> None:
    headers = _headers("date-validation")

    missing = client.get("/invoices/next-number", headers=headers)
    invalid = client.get(
        "/invoices/next-number",
        headers=headers,
        params={"issue_date": "not-a-date"},
    )

    assert missing.status_code == 422
    assert invalid.status_code == 422


def test_next_number_static_route_is_not_captured_as_invoice_id() -> None:
    headers = _headers("route-order")

    response = client.get(
        "/invoices/next-number",
        headers=headers,
        params={"issue_date": "2026-08-10"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"invoice_number": "2026/08/0001"}


def test_existing_duplicate_invoice_number_contract_remains_409() -> None:
    headers = _headers("duplicate")
    invoice_number = f"DUP-{uuid4().hex[:12]}"
    _create_invoice(headers, invoice_number)

    duplicate = client.post(
        "/invoices",
        headers=headers,
        json=_payload(invoice_number),
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Invoice number already exists for this tenant"
    }
