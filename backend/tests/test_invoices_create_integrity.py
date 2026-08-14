from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.main import app
from app.routes import invoices as invoices_route
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from tests.invoice_profile_helpers import save_complete_profile


client = TestClient(app)


def _headers(prefix: str = "invoice-integrity") -> dict[str, str]:
    headers = {"X-Tenant-Code": f"ii-{uuid4().hex[:12]}-{prefix}"}
    save_complete_profile(client, headers)
    return headers


def _payload(invoice_number: str | None = None, **overrides) -> dict:
    payload = {
        "invoice_number": invoice_number or f"INT-{uuid4().hex[:12]}",
        "issue_date": "2090-01-10",
        "due_date": "2090-01-20",
        "buyer_type": "BUSINESS",
        "buyer_name": "Integrity Buyer",
        "buyer_address": "Test address",
        "buyer_tax_id": "4401234560001",
        "note": "Test note",
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
    payload.update(overrides)
    return payload


def test_create_trims_required_and_optional_text() -> None:
    response = client.post(
        "/invoices",
        headers=_headers("invoice-trim"),
        json=_payload(
            f"  TRIM-{uuid4().hex[:10]}  ",
            buyer_name="  Trimmed Buyer  ",
            buyer_address="  Trimmed address  ",
            buyer_tax_id="  4401234560001  ",
            note="  Trimmed note  ",
            items=[
                {
                    "description": "  Trimmed service  ",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "vat_rate": "0.17",
                }
            ],
        ),
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["invoice_number"].startswith("TRIM-")
    assert not created["invoice_number"].startswith(" ")
    assert not created["invoice_number"].endswith(" ")
    assert created["buyer_name"] == "Trimmed Buyer"
    assert created["buyer_address"] == "Trimmed address"
    assert created["buyer_tax_id"] == "4401234560001"
    assert created["note"] == "Trimmed note"
    assert created["items"][0]["description"] == "Trimmed service"


@pytest.mark.parametrize("field", ["invoice_number", "buyer_name", "description"])
def test_whitespace_only_required_text_is_rejected(field: str) -> None:
    payload = _payload()
    if field == "description":
        payload["items"][0]["description"] = "   "
    else:
        payload[field] = "   "

    response = client.post(
        "/invoices",
        headers=_headers(f"invoice-required-{field}"),
        json=payload,
    )

    assert response.status_code == 422


def test_whitespace_optional_text_becomes_none() -> None:
    response = client.post(
        "/invoices",
        headers=_headers("invoice-optional"),
        json=_payload(
            buyer_type="INDIVIDUAL",
            buyer_address="   ",
            buyer_tax_id="   ",
            note="   ",
        ),
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["buyer_address"] is None
    assert created["buyer_tax_id"] is None
    assert created["note"] is None


def test_db_aligned_maximum_lengths_are_accepted() -> None:
    response = client.post(
        "/invoices",
        headers=_headers("invoice-max"),
        json=_payload(
            "N" * 32,
            buyer_name="B" * 128,
            buyer_address="A" * 256,
            buyer_tax_id="T" * 64,
        ),
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("invoice_number", "N" * 33),
        ("buyer_name", "B" * 129),
        ("buyer_address", "A" * 257),
        ("buyer_tax_id", "T" * 65),
    ],
)
def test_values_over_db_aligned_maximum_are_rejected(
    field: str,
    value: str,
) -> None:
    response = client.post(
        "/invoices",
        headers=_headers(f"invoice-too-long-{field}"),
        json=_payload(**{field: value}),
    )

    assert response.status_code == 422


def test_trim_happens_before_length_validation() -> None:
    invoice_number = "N" * 32
    response = client.post(
        "/invoices",
        headers=_headers("invoice-trim-length"),
        json=_payload(f"  {invoice_number}  "),
    )

    assert response.status_code == 201, response.text
    assert response.json()["invoice_number"] == invoice_number


@pytest.mark.parametrize(
    ("due_date", "expected_status"),
    [
        ("2090-01-09", 422),
        ("2090-01-10", 201),
        ("2090-01-11", 201),
        (None, 201),
    ],
)
def test_due_date_must_not_precede_issue_date(
    due_date: str | None,
    expected_status: int,
) -> None:
    response = client.post(
        "/invoices",
        headers=_headers("invoice-due-date"),
        json=_payload(due_date=due_date),
    )

    assert response.status_code == expected_status, response.text
    if expected_status == 422:
        assert "due_date must be on or after issue_date" in response.text


def test_client_totals_are_ignored_and_absent_from_create_schema() -> None:
    payload = _payload()
    payload["items"][0].update(
        {
            "base_amount": "999999.99",
            "vat_amount": "999999.99",
            "total_amount": "999999.99",
        }
    )

    response = client.post(
        "/invoices",
        headers=_headers("invoice-authoritative"),
        json=payload,
    )

    assert response.status_code == 201, response.text
    item = response.json()["items"][0]
    assert item["base_amount"] == "100.00"
    assert item["vat_amount"] == "17.00"
    assert item["total_amount"] == "117.00"

    properties = InvoiceItemCreate.model_json_schema()["properties"]
    assert "base_amount" not in properties
    assert "vat_amount" not in properties
    assert "total_amount" not in properties


def test_trimmed_duplicate_keeps_existing_409_contract() -> None:
    headers = _headers("invoice-duplicate")
    invoice_number = f"DUP-{uuid4().hex[:10]}"

    first = client.post(
        "/invoices",
        headers=headers,
        json=_payload(f"  {invoice_number}  "),
    )
    duplicate = client.post(
        "/invoices",
        headers=headers,
        json=_payload(invoice_number),
    )

    assert first.status_code == 201, first.text
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Invoice number already exists for this tenant"
    }


def test_same_invoice_number_is_allowed_for_different_tenants() -> None:
    invoice_number = f"SHARED-{uuid4().hex[:10]}"
    first = client.post(
        "/invoices",
        headers=_headers("invoice-tenant-a"),
        json=_payload(invoice_number),
    )
    second = client.post(
        "/invoices",
        headers=_headers("invoice-tenant-b"),
        json=_payload(invoice_number),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


class _FailingSession:
    def __init__(self, constraint_name: str | None) -> None:
        self.events: list[str] = []
        original = RuntimeError("private driver details")
        original.diag = SimpleNamespace(constraint_name=constraint_name)
        self.error = IntegrityError(
            "INSERT private SQL",
            {"private": "parameter"},
            original,
        )

    def add(self, _value) -> None:
        self.events.append("add")

    def commit(self) -> None:
        self.events.append("commit")
        raise self.error

    def rollback(self) -> None:
        self.events.append("rollback")


@pytest.mark.parametrize("constraint_name", ["ck_other_constraint", None])
def test_unexpected_integrity_error_is_generic_after_rollback(
    monkeypatch: pytest.MonkeyPatch,
    constraint_name: str | None,
) -> None:
    db = _FailingSession(constraint_name)
    monkeypatch.setattr(invoices_route, "_ensure_tenant_exists", lambda *_args: None)
    monkeypatch.setattr(
        invoices_route,
        "_get_invoice_issuer_snapshot",
        lambda *_args: {
            "issuer_business_name": "Issuer",
            "issuer_address": "Address",
            "issuer_tax_id": "Tax ID",
        },
    )
    original_helper = invoices_route._integrity_constraint_name

    def constraint_after_rollback(exc: IntegrityError) -> str | None:
        assert db.events[-1] == "rollback"
        return original_helper(exc)

    monkeypatch.setattr(
        invoices_route,
        "_integrity_constraint_name",
        constraint_after_rollback,
    )

    with pytest.raises(HTTPException) as captured:
        invoices_route.create_invoice(
            payload=InvoiceCreate.model_validate(_payload()),
            db=db,
            x_tenant_code="integrity-error-tenant",
        )

    assert captured.value.status_code == 500
    assert captured.value.detail == invoices_route.UNEXPECTED_INTEGRITY_ERROR_MESSAGE
    assert "private" not in captured.value.detail
    assert db.events == ["add", "commit", "rollback"]


def test_constraint_helper_recognizes_only_named_unique_constraint() -> None:
    expected = _FailingSession(
        invoices_route.INVOICE_NUMBER_UNIQUE_CONSTRAINT
    ).error
    other = _FailingSession("another_constraint").error
    missing = _FailingSession(None).error

    assert (
        invoices_route._integrity_constraint_name(expected)
        == invoices_route.INVOICE_NUMBER_UNIQUE_CONSTRAINT
    )
    assert invoices_route._integrity_constraint_name(other) == "another_constraint"
    assert invoices_route._integrity_constraint_name(missing) is None


def test_invoice_requests_do_not_execute_runtime_ddl() -> None:
    statements: list[str] = []

    def record_statement(
        _conn,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        headers = _headers("invoice-no-ddl")
        created = client.post("/invoices", headers=headers, json=_payload())
        assert created.status_code == 201, created.text
        invoice_id = created.json()["id"]

        listed = client.get("/invoices/list", headers=headers)
        exported = client.get("/invoices/export", headers=headers)
        marked = client.post(f"/invoices/{invoice_id}/mark-paid", headers=headers)

        assert listed.status_code == 200, listed.text
        assert exported.status_code == 200, exported.text
        assert marked.status_code == 200, marked.text
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert not hasattr(invoices_route, "_ensure_is_paid_column")
    assert all("alter table" not in statement.lower() for statement in statements)
