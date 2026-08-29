from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import InputInvoice, Invoice
from app.tenant_security import ensure_tenant_exists


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers(prefix: str) -> dict[str, str]:
    return {"X-Tenant-Code": f"{prefix}-{uuid4().hex[:10]}"}


def _create_invoice_pair(tenant_code: str) -> tuple[int, int]:
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant_code)
        suffix = uuid4().hex[:10]
        invoice = Invoice(
            tenant_code=tenant_code,
            invoice_number=f"OUT-{suffix}",
            issue_date=date(2025, 11, 1),
            buyer_name="Cash link buyer",
            total_base=Decimal("10.00"),
            total_vat=Decimal("0.00"),
            total_amount=Decimal("10.00"),
        )
        input_invoice = InputInvoice(
            tenant_code=tenant_code,
            supplier_name="Cash link supplier",
            invoice_number=f"IN-{suffix}",
            issue_date=date(2025, 11, 1),
            total_base=Decimal("10.00"),
            total_vat=Decimal("0.00"),
            total_amount=Decimal("10.00"),
        )
        db.add_all([invoice, input_invoice])
        db.commit()
        db.refresh(invoice)
        db.refresh(input_invoice)
        return invoice.id, input_invoice.id


def _cash_payload(**overrides) -> dict:
    payload = {
        "entry_date": "2025-11-07",
        "kind": "expense",
        "amount": "12.34",
        "note": f"cash-link-{uuid4().hex[:10]}",
    }
    payload.update(overrides)
    return payload


def _create_cash(
    client: TestClient,
    headers: dict[str, str],
    **overrides,
) -> dict:
    response = client.post(
        "/cash/",
        headers=headers,
        json=_cash_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assert_extra_forbidden(response, field_name: str) -> None:
    assert response.status_code == 422, response.text

    details = response.json()["detail"]
    assert any(
        item.get("type") == "extra_forbidden"
        and item.get("loc") == ["body", field_name]
        for item in details
    ), response.text


def test_create_rejects_same_tenant_outgoing_invoice_link(
    client: TestClient,
) -> None:
    headers = _headers("cash-link-valid")
    invoice_id, _ = _create_invoice_pair(headers["X-Tenant-Code"])

    response = client.post(
        "/cash/",
        headers=headers,
        json=_cash_payload(invoice_id=invoice_id),
    )

    _assert_extra_forbidden(response, "invoice_id")

    listed = client.get("/cash/", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []

def test_create_rejects_input_invoice_link(client: TestClient) -> None:
    headers = _headers("cash-input-link-rejected")
    _, input_invoice_id = _create_invoice_pair(headers["X-Tenant-Code"])

    response = client.post(
        "/cash/",
        headers=headers,
        json=_cash_payload(input_invoice_id=input_invoice_id),
    )

    _assert_extra_forbidden(response, "input_invoice_id")

    listed = client.get("/cash/", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []


def test_create_rejects_cross_tenant_outgoing_invoice_link(
    client: TestClient,
) -> None:
    owner_headers = _headers("cash-link-owner")
    requester_headers = _headers("cash-link-requester")
    invoice_id, _ = _create_invoice_pair(owner_headers["X-Tenant-Code"])

    response = client.post(
        "/cash/",
        headers=requester_headers,
        json=_cash_payload(invoice_id=invoice_id),
    )

    _assert_extra_forbidden(response, "invoice_id")

    listed = client.get("/cash/", headers=requester_headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []


def test_create_rejects_missing_outgoing_invoice_link(
    client: TestClient,
) -> None:
    headers = _headers("cash-link-missing")

    response = client.post(
        "/cash/",
        headers=headers,
        json=_cash_payload(invoice_id=9_999_999_999),
    )

    _assert_extra_forbidden(response, "invoice_id")


def test_patch_rejects_outgoing_invoice_link_and_unlink_fields(
    client: TestClient,
) -> None:
    headers = _headers("cash-link-patch")
    invoice_id, _ = _create_invoice_pair(headers["X-Tenant-Code"])
    created = _create_cash(client, headers)
    cash_id = created["id"]

    linked = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={"invoice_id": invoice_id},
    )
    _assert_extra_forbidden(linked, "invoice_id")

    unlinked = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={"invoice_id": None},
    )
    _assert_extra_forbidden(unlinked, "invoice_id")

    stored = client.get(f"/cash/{cash_id}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["invoice_id"] is None
    assert stored.json()["input_invoice_id"] is None


def test_patch_rejects_input_invoice_link_and_preserves_existing_data(
    client: TestClient,
) -> None:
    headers = _headers("cash-input-link-patch")
    _, input_invoice_id = _create_invoice_pair(
        headers["X-Tenant-Code"]
    )
    created = _create_cash(client, headers)
    cash_id = created["id"]

    rejected = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={"input_invoice_id": input_invoice_id},
    )

    _assert_extra_forbidden(rejected, "input_invoice_id")

    stored = client.get(f"/cash/{cash_id}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["invoice_id"] is None
    assert stored.json()["input_invoice_id"] is None


@pytest.mark.parametrize(
    "use_missing",
    [False, True],
)
def test_generic_cash_patch_rejects_outgoing_invoice_reference(
    client: TestClient,
    use_missing: bool,
) -> None:
    headers = _headers("cash-link-safe")
    other_headers = _headers("cash-link-other")

    _, _ = _create_invoice_pair(headers["X-Tenant-Code"])
    other_invoice_id, _ = _create_invoice_pair(
        other_headers["X-Tenant-Code"]
    )

    created = _create_cash(client, headers)
    cash_id = created["id"]

    invalid_id = 9_999_999_999 if use_missing else other_invoice_id

    rejected = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={"invoice_id": invalid_id},
    )

    _assert_extra_forbidden(rejected, "invoice_id")

    stored = client.get(f"/cash/{cash_id}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["invoice_id"] is None
    assert stored.json()["input_invoice_id"] is None

def _create_output_payment(
    client: TestClient,
    headers: dict[str, str],
    invoice_id: int,
) -> dict:
    response = client.post(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
        json={
            "payment_date": "2025-11-07",
            "account": "bank",
            "note": "Protected output payment",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_output_payment_cannot_be_patched_through_generic_cash(
    client: TestClient,
) -> None:
    headers = _headers("cash-output-payment-patch")
    invoice_id, _ = _create_invoice_pair(headers["X-Tenant-Code"])
    payment = _create_output_payment(client, headers, invoice_id)

    response = client.patch(
        f"/cash/{payment['id']}",
        headers=headers,
        json={"amount": "999.99"},
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "Invoice payments must be changed through the "
            "invoice payment endpoint"
        )
    }

    stored = client.get(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
    )
    assert stored.status_code == 200, stored.text
    assert Decimal(stored.json()["amount"]) == Decimal("10.00")


def test_output_payment_cannot_be_deleted_through_generic_cash(
    client: TestClient,
) -> None:
    headers = _headers("cash-output-payment-delete")
    invoice_id, _ = _create_invoice_pair(headers["X-Tenant-Code"])
    payment = _create_output_payment(client, headers, invoice_id)

    response = client.delete(
        f"/cash/{payment['id']}",
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "Invoice payments must be removed through the "
            "invoice payment endpoint"
        )
    }

    stored = client.get(
        f"/invoices/{invoice_id}/payment",
        headers=headers,
    )
    assert stored.status_code == 200, stored.text

def _create_input_payment(
    client: TestClient,
    headers: dict[str, str],
    input_invoice_id: int,
) -> dict:
    response = client.post(
        f"/input-invoices/{input_invoice_id}/payment",
        headers=headers,
        json={
            "payment_date": "2025-11-08",
            "account": "cash",
            "note": "Protected input payment",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cash_list_exposes_invoice_payment_sources(
    client: TestClient,
) -> None:
    headers = _headers("cash-source-metadata")
    tenant_code = headers["X-Tenant-Code"]

    invoice_id, input_invoice_id = _create_invoice_pair(tenant_code)

    output_payment = _create_output_payment(
        client,
        headers,
        invoice_id,
    )
    input_payment = _create_input_payment(
        client,
        headers,
        input_invoice_id,
    )

    manual = _create_cash(
        client,
        headers,
        entry_date="2025-11-09",
        kind="income",
        account="cash",
        note="Manual source",
    )

    response = client.get(
        "/cash/list",
        headers=headers,
        params={"limit": 20, "offset": 0},
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["total"] == 3
    assert data["limit"] == 20
    assert data["offset"] == 0

    rows = {row["id"]: row for row in data["items"]}

    output_row = rows[output_payment["id"]]
    assert output_row["source_type"] == "output_invoice_payment"
    assert output_row["source_document_id"] == invoice_id
    assert output_row["source_document_number"].startswith("OUT-")
    assert output_row["source_party_name"] == "Cash link buyer"

    input_row = rows[input_payment["id"]]
    assert input_row["source_type"] == "input_invoice_payment"
    assert input_row["source_document_id"] == input_invoice_id
    assert input_row["source_document_number"].startswith("IN-")
    assert input_row["source_party_name"] == "Cash link supplier"

    manual_row = rows[manual["id"]]
    assert manual_row["source_type"] == "manual"
    assert manual_row["source_document_id"] is None
    assert manual_row["source_document_number"] is None
    assert manual_row["source_party_name"] is None

    for source_type, expected_id in [
        ("manual", manual["id"]),
        ("output_invoice_payment", output_payment["id"]),
        ("input_invoice_payment", input_payment["id"]),
    ]:
        filtered = client.get(
            "/cash/list",
            headers=headers,
            params={"source_type": source_type},
        )
        assert filtered.status_code == 200, filtered.text

        filtered_data = filtered.json()
        assert filtered_data["total"] == 1
        assert [row["id"] for row in filtered_data["items"]] == [
            expected_id
        ]
