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


def test_create_accepts_same_tenant_invoice_links(client: TestClient) -> None:
    headers = _headers("cash-link-valid")
    invoice_id, input_invoice_id = _create_invoice_pair(
        headers["X-Tenant-Code"]
    )

    created = _create_cash(
        client,
        headers,
        invoice_id=invoice_id,
        input_invoice_id=input_invoice_id,
    )

    assert created["invoice_id"] == invoice_id
    assert created["input_invoice_id"] == input_invoice_id


@pytest.mark.parametrize(
    ("field", "detail"),
    [
        ("invoice_id", "Invoice not found"),
        ("input_invoice_id", "Input invoice not found"),
    ],
)
def test_create_rejects_cross_tenant_invoice_links(
    client: TestClient,
    field: str,
    detail: str,
) -> None:
    owner_headers = _headers("cash-link-owner")
    requester_headers = _headers("cash-link-requester")
    invoice_id, input_invoice_id = _create_invoice_pair(
        owner_headers["X-Tenant-Code"]
    )
    linked_id = invoice_id if field == "invoice_id" else input_invoice_id

    response = client.post(
        "/cash/",
        headers=requester_headers,
        json=_cash_payload(**{field: linked_id}),
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": detail}
    listed = client.get("/cash/", headers=requester_headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []


@pytest.mark.parametrize(
    ("field", "detail"),
    [
        ("invoice_id", "Invoice not found"),
        ("input_invoice_id", "Input invoice not found"),
    ],
)
def test_create_rejects_missing_invoice_links(
    client: TestClient,
    field: str,
    detail: str,
) -> None:
    headers = _headers("cash-link-missing")

    response = client.post(
        "/cash/",
        headers=headers,
        json=_cash_payload(**{field: 9_999_999_999}),
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": detail}


def test_patch_validates_preserves_and_unlinks_references(
    client: TestClient,
) -> None:
    headers = _headers("cash-link-patch")
    invoice_id, input_invoice_id = _create_invoice_pair(
        headers["X-Tenant-Code"]
    )
    created = _create_cash(client, headers)
    cash_id = created["id"]

    linked = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={
            "invoice_id": invoice_id,
            "input_invoice_id": input_invoice_id,
        },
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["invoice_id"] == invoice_id
    assert linked.json()["input_invoice_id"] == input_invoice_id

    preserved = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={"amount": "22.22"},
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["invoice_id"] == invoice_id
    assert preserved.json()["input_invoice_id"] == input_invoice_id

    unlinked = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={"invoice_id": None, "input_invoice_id": None},
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["invoice_id"] is None
    assert unlinked.json()["input_invoice_id"] is None


@pytest.mark.parametrize(
    ("field", "use_missing", "detail"),
    [
        ("invoice_id", False, "Invoice not found"),
        ("input_invoice_id", False, "Input invoice not found"),
        ("invoice_id", True, "Invoice not found"),
    ],
)
def test_rejected_patch_does_not_change_existing_links(
    client: TestClient,
    field: str,
    use_missing: bool,
    detail: str,
) -> None:
    headers = _headers("cash-link-safe")
    other_headers = _headers("cash-link-other")
    invoice_id, input_invoice_id = _create_invoice_pair(
        headers["X-Tenant-Code"]
    )
    other_invoice_id, other_input_invoice_id = _create_invoice_pair(
        other_headers["X-Tenant-Code"]
    )
    created = _create_cash(
        client,
        headers,
        invoice_id=invoice_id,
        input_invoice_id=input_invoice_id,
    )
    cash_id = created["id"]
    invalid_id = 9_999_999_999
    if not use_missing:
        invalid_id = (
            other_invoice_id
            if field == "invoice_id"
            else other_input_invoice_id
        )

    rejected = client.patch(
        f"/cash/{cash_id}",
        headers=headers,
        json={field: invalid_id},
    )

    assert rejected.status_code == 404, rejected.text
    assert rejected.json() == {"detail": detail}
    stored = client.get(f"/cash/{cash_id}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["invoice_id"] == invoice_id
    assert stored.json()["input_invoice_id"] == input_invoice_id
