from __future__ import annotations

import csv
import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import invoices as invoices_route
from tests.invoice_profile_helpers import save_complete_profile


client = TestClient(app)
EXPECTED_HEADER = [
    "Broj fakture",
    "Datum izdavanja",
    "Rok plaćanja",
    "Kupac",
    "Ukupan iznos",
    "Plaćena",
]


def _headers(prefix: str) -> dict[str, str]:
    headers = {"X-Tenant-Code": f"csv-{uuid4().hex[:12]}-{prefix}"}
    save_complete_profile(client, headers)
    return headers


def _payload(
    invoice_number: str,
    *,
    buyer_name: str = "CSV Buyer",
    issue_date: str = "2091-02-10",
    due_date: str | None = "2091-02-20",
) -> dict:
    return {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "due_date": due_date,
        "buyer_type": "BUSINESS",
        "buyer_name": buyer_name,
        "buyer_address": "CSV address",
        "buyer_tax_id": "4401234560001",
        "items": [
            {
                "description": "CSV service",
                "quantity": "1",
                "unit_price": "100.00",
                "discount_percent": "0",
                "vat_rate": "0.17",
            }
        ],
    }


def _create(headers: dict[str, str], payload: dict) -> dict:
    response = client.post("/invoices", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _parse_export(response) -> list[list[str]]:
    assert response.content.startswith(b"\xff\xfe")
    text = response.content.decode("utf-16")
    first_line, separator, csv_body = text.partition("\r\n")
    assert first_line == "sep=;"
    assert separator == "\r\n"
    return list(csv.reader(io.StringIO(csv_body), delimiter=";"))


def test_invoice_export_empty_contract() -> None:
    headers = _headers("empty")

    response = client.get("/invoices/export", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/csv; charset=utf-16le"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="invoices-export.csv"'
    )
    assert _parse_export(response) == [EXPECTED_HEADER]


def test_invoice_export_quotes_business_text_and_formats_values() -> None:
    headers = _headers("quoting")
    special_number = 'CSV;,"Q"'
    special_buyer = 'Žuti; kupac,\n"Nova"'
    unpaid = _create(
        headers,
        _payload(
            special_number,
            buyer_name=special_buyer,
            due_date=None,
        ),
    )
    paid = _create(
        headers,
        _payload(
            f"PAID-{uuid4().hex[:8]}",
            buyer_name="Plaćeni kupac",
            issue_date="2091-02-11",
        ),
    )
    marked = client.post(
        f"/invoices/{paid['id']}/mark-paid",
        headers=headers,
    )
    assert marked.status_code == 200, marked.text

    response = client.get("/invoices/export", headers=headers)
    parsed = _parse_export(response)

    assert parsed[0] == EXPECTED_HEADER
    rows = {row[0]: row for row in parsed[1:]}
    assert rows[special_number] == [
        special_number,
        "2091-02-10",
        "",
        special_buyer,
        "117.00",
        "NE",
    ]
    assert "Žuti" in rows[special_number][3]
    assert rows[paid["invoice_number"]][5] == "DA"
    assert len(rows[paid["invoice_number"]]) == 6
    assert len(rows[special_number]) == 6
    assert unpaid["is_paid"] is False


@pytest.mark.parametrize("dangerous_prefix", ["=", "+", "-", "@"])
@pytest.mark.parametrize("field", ["invoice_number", "buyer_name"])
def test_invoice_export_protects_formula_prefixes(
    dangerous_prefix: str,
    field: str,
) -> None:
    headers = _headers(f"formula-{field}")
    invoice_number = f"FORM-{uuid4().hex[:8]}"
    buyer_name = "Formula Buyer"
    dangerous_value = f"{dangerous_prefix}SUM(1,1)"
    if field == "invoice_number":
        invoice_number = dangerous_value
    else:
        buyer_name = dangerous_value

    _create(
        headers,
        _payload(invoice_number, buyer_name=buyer_name),
    )

    parsed = _parse_export(client.get("/invoices/export", headers=headers))
    exported = parsed[1][0 if field == "invoice_number" else 3]
    assert exported == f"'{dangerous_value}"


def test_formula_protection_detects_prefix_after_whitespace_and_controls() -> None:
    value = " \t\x01=SUM(1,1)"
    assert invoices_route._protect_spreadsheet_text(value) == f"'{value}"
    assert invoices_route._protect_spreadsheet_text("Normal value") == "Normal value"


def test_invoice_export_respects_filters_and_tenant_isolation() -> None:
    first_headers = _headers("filters-a")
    second_headers = _headers("filters-b")

    target = _create(
        first_headers,
        _payload(
            f"TARGET-{uuid4().hex[:8]}",
            buyer_name="Target Buyer",
            issue_date="2091-02-10",
        ),
    )
    _create(
        first_headers,
        _payload(
            f"OTHER-{uuid4().hex[:8]}",
            buyer_name="Other Buyer",
            issue_date="2091-03-10",
            due_date="2091-03-20",
        ),
    )
    _create(
        second_headers,
        _payload(
            f"FOREIGN-{uuid4().hex[:8]}",
            buyer_name="Target Buyer",
            issue_date="2091-02-10",
        ),
    )

    response = client.get(
        "/invoices/export",
        headers=first_headers,
        params={
            "year": 2091,
            "month": 2,
            "buyer_query": "target",
            "unpaid_only": "true",
        },
    )
    parsed = _parse_export(response)

    assert parsed == [
        EXPECTED_HEADER,
        [
            target["invoice_number"],
            "2091-02-10",
            "2091-02-20",
            "Target Buyer",
            "117.00",
            "NE",
        ],
    ]

    empty = client.get(
        "/invoices/export",
        headers=first_headers,
        params={"buyer_query": "does-not-exist"},
    )
    assert _parse_export(empty) == [EXPECTED_HEADER]
