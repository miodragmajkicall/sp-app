from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session as _get_session_dep
from app.main import app
from app.models import Invoice, TenantProfileSettings
from tests.invoice_profile_helpers import COMPLETE_PROFILE, save_complete_profile


client = TestClient(app)
PROFILE_ERROR = "Company profile must be completed before issuing an invoice"
ISSUER_FIELDS = (
    "issuer_business_name",
    "issuer_address",
    "issuer_tax_id",
    "issuer_phone",
    "issuer_email",
    "issuer_bank_name",
    "issuer_bank_account",
    "issuer_iban",
    "issuer_swift_bic",
)


def _headers(prefix: str = "issuer-snapshot") -> dict[str, str]:
    return {"X-Tenant-Code": f"{prefix}-{uuid4().hex[:12]}"}


def _payload(invoice_number: str, **extra) -> dict:
    return {
        "invoice_number": invoice_number,
        "issue_date": "2089-01-10",
        "due_date": "2089-01-20",
        "buyer_type": "BUSINESS",
        "buyer_name": "Snapshot Buyer",
        "buyer_address": "Buyer address",
        "items": [
            {
                "description": "Snapshot service",
                "quantity": "1",
                "unit_price": "100.00",
                "vat_rate": "0.17",
            }
        ],
        **extra,
    }


@contextmanager
def _db_session():
    generator = _get_session_dep()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def _assert_profile_error(response) -> None:
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": PROFILE_ERROR}


def test_missing_profile_returns_exact_409_and_does_not_create_invoice() -> None:
    headers = _headers("issuer-missing")
    invoice_number = f"MISS-{uuid4().hex[:10]}"

    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(invoice_number),
    )
    _assert_profile_error(response)

    listed = client.get("/invoices", headers=headers)
    assert listed.status_code == 200
    assert all(row["invoice_number"] != invoice_number for row in listed.json())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("business_name", ""),
        ("business_name", "   "),
        ("address", None),
        ("address", ""),
        ("address", "   "),
        ("tax_id", None),
        ("tax_id", ""),
        ("tax_id", "   "),
    ],
)
def test_incomplete_required_profile_values_return_exact_409(
    field: str,
    value: str | None,
) -> None:
    headers = _headers(f"issuer-invalid-{field}")
    save_complete_profile(client, headers, **{field: value})

    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(f"INVALID-{uuid4().hex[:10]}"),
    )
    _assert_profile_error(response)


def test_complete_profile_is_trimmed_snapshotted_and_note_is_persisted() -> None:
    headers = _headers("issuer-complete")
    profile = {
        "business_name": "  Snapshot Issuer SP  ",
        "address": "  Main street 10  ",
        "tax_id": "  4401234560001  ",
        "phone": "  +387 51 123 456  ",
        "email": "  office@example.ba  ",
        "bank_name": "  Snapshot Bank  ",
        "bank_account": "  555-123-99  ",
        "iban": "  BA391290079401028494  ",
        "swift_bic": "  SNAPBA22  ",
    }
    saved = save_complete_profile(client, headers, **profile)

    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(
            f"FULL-{uuid4().hex[:10]}",
            note="Historical note",
            issuer_business_name="Client supplied issuer",
        ),
    )
    assert response.status_code == 201, response.text
    created = response.json()

    expected = {
        "issuer_business_name": "Snapshot Issuer SP",
        "issuer_address": "Main street 10",
        "issuer_tax_id": "4401234560001",
        "issuer_phone": saved["phone"],
        "issuer_email": saved["email"],
        "issuer_bank_name": saved["bank_name"],
        "issuer_bank_account": saved["bank_account"],
        "issuer_iban": saved["iban"],
        "issuer_swift_bic": saved["swift_bic"],
    }
    for field, value in expected.items():
        assert created[field] == value
    assert created["issuer_business_name"] != "Client supplied issuer"
    assert created["note"] == "Historical note"

    detail = client.get(f"/invoices/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["note"] == "Historical note"
    for field, value in expected.items():
        assert detail.json()[field] == value


def test_empty_optional_profile_values_are_snapshotted_as_none() -> None:
    headers = _headers("issuer-optional")
    save_complete_profile(
        client,
        headers,
        phone=" ",
        email="",
        bank_name="  ",
        bank_account="",
        iban="\t",
        swift_bic="\n",
    )

    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(f"OPTIONAL-{uuid4().hex[:10]}"),
    )
    assert response.status_code == 201, response.text
    for field in ISSUER_FIELDS[3:]:
        assert response.json()[field] is None


def test_profile_from_another_tenant_is_never_used() -> None:
    owner_headers = _headers("issuer-owner")
    target_headers = _headers("issuer-target")
    save_complete_profile(client, owner_headers)

    response = client.post(
        "/invoices",
        headers=target_headers,
        json=_payload(f"CROSS-{uuid4().hex[:10]}"),
    )
    _assert_profile_error(response)


def test_existing_snapshot_is_immutable_and_new_invoice_uses_updated_profile() -> None:
    headers = _headers("issuer-history")
    save_complete_profile(client, headers, business_name="Issuer Before")

    first = client.post(
        "/invoices",
        headers=headers,
        json=_payload(f"BEFORE-{uuid4().hex[:10]}"),
    )
    assert first.status_code == 201, first.text

    save_complete_profile(
        client,
        headers,
        business_name="Issuer After",
        address="Updated address",
        tax_id="4409999999999",
    )

    first_detail = client.get(f"/invoices/{first.json()['id']}", headers=headers)
    assert first_detail.status_code == 200
    assert first_detail.json()["issuer_business_name"] == "Issuer Before"
    assert first_detail.json()["issuer_address"] == COMPLETE_PROFILE["address"]

    second = client.post(
        "/invoices",
        headers=headers,
        json=_payload(f"AFTER-{uuid4().hex[:10]}"),
    )
    assert second.status_code == 201, second.text
    assert second.json()["issuer_business_name"] == "Issuer After"
    assert second.json()["issuer_address"] == "Updated address"
    assert second.json()["issuer_tax_id"] == "4409999999999"


def test_duplicate_invoice_number_keeps_existing_409_message() -> None:
    headers = _headers("issuer-duplicate")
    save_complete_profile(client, headers)
    invoice_number = f"DUP-{uuid4().hex[:10]}"
    payload = _payload(invoice_number)

    first = client.post("/invoices", headers=headers, json=payload)
    assert first.status_code == 201, first.text

    duplicate = client.post("/invoices", headers=headers, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Invoice number already exists for this tenant"
    }


def test_legacy_null_snapshot_remains_readable_and_markable_paid() -> None:
    headers = _headers("issuer-legacy")
    save_complete_profile(client, headers)
    created = client.post(
        "/invoices",
        headers=headers,
        json=_payload(f"LEGACY-{uuid4().hex[:10]}"),
    )
    assert created.status_code == 201, created.text

    with _db_session() as db:
        invoice = db.execute(
            select(Invoice).where(Invoice.id == created.json()["id"])
        ).scalar_one()
        for field in ISSUER_FIELDS:
            setattr(invoice, field, None)
        db.commit()

    detail = client.get(f"/invoices/{created.json()['id']}", headers=headers)
    assert detail.status_code == 200
    for field in ISSUER_FIELDS:
        assert detail.json()[field] is None

    marked = client.post(
        f"/invoices/{created.json()['id']}/mark-paid",
        headers=headers,
    )
    assert marked.status_code == 200
    for field in ISSUER_FIELDS:
        assert marked.json()[field] is None
