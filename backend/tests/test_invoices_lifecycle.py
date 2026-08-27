from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import InvoiceItem
from tests.invoice_profile_helpers import save_complete_profile


client = TestClient(app)


def _headers(prefix: str) -> dict[str, str]:
    headers = {"X-Tenant-Code": f"lifecycle-{prefix}-{uuid4().hex[:10]}"}
    save_complete_profile(client, headers)
    return headers


def _payload(
    *,
    issue_date: str = "2091-01-10",
    buyer_name: str = "Lifecycle Buyer",
    item_count: int = 1,
) -> dict:
    return {
        "invoice_number": f"LIFE-{uuid4().hex[:12]}",
        "issue_date": issue_date,
        "due_date": issue_date,
        "buyer_type": "BUSINESS",
        "buyer_name": buyer_name,
        "buyer_address": "Lifecycle address",
        "buyer_tax_id": "4401234560001",
        "note": "Lifecycle test",
        "items": [
            {
                "description": f"Lifecycle service {index + 1}",
                "quantity": "1.00",
                "unit_price": f"{100 + index}.00",
                "discount_percent": "0.00",
                "vat_rate": "0.17",
            }
            for index in range(item_count)
        ],
    }


def _create_invoice(
    headers: dict[str, str],
    *,
    issue_date: str = "2091-01-10",
    buyer_name: str = "Lifecycle Buyer",
    item_count: int = 1,
) -> dict:
    response = client.post(
        "/invoices",
        headers=headers,
        json=_payload(
            issue_date=issue_date,
            buyer_name=buyer_name,
            item_count=item_count,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_list_empty_pagination_and_stable_order() -> None:
    headers = _headers("list")

    empty = client.get("/invoices/list", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"total": 0, "items": []}

    created = [
        _create_invoice(headers, issue_date=issue_date)
        for issue_date in (
            "2091-01-01",
            "2091-01-03",
            "2091-01-02",
            "2091-01-03",
        )
    ]
    expected_ids = [
        invoice["id"]
        for invoice in sorted(
            created,
            key=lambda invoice: (invoice["issue_date"], invoice["id"]),
            reverse=True,
        )
    ]

    first_page = client.get(
        "/invoices/list",
        headers=headers,
        params={"page": 1, "page_size": 2},
    )
    second_page = client.get(
        "/invoices/list",
        headers=headers,
        params={"page": 2, "page_size": 2},
    )
    offset_page = client.get(
        "/invoices/list",
        headers=headers,
        params={"limit": 2, "offset": 2},
    )

    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert offset_page.status_code == 200, offset_page.text
    assert first_page.json()["total"] == 4
    assert second_page.json()["total"] == 4
    assert offset_page.json()["total"] == 4

    first_ids = [item["id"] for item in first_page.json()["items"]]
    second_ids = [item["id"] for item in second_page.json()["items"]]
    offset_ids = [item["id"] for item in offset_page.json()["items"]]
    assert first_ids == expected_ids[:2]
    assert second_ids == expected_ids[2:]
    assert offset_ids == expected_ids[2:]
    assert set(first_ids).isdisjoint(second_ids)


def test_list_filters_and_totals_share_the_filtered_set() -> None:
    headers = _headers("filters")
    alpha_january = _create_invoice(
        headers,
        issue_date="2091-01-10",
        buyer_name="Alpha Services",
    )
    alpha_february = _create_invoice(
        headers,
        issue_date="2091-02-10",
        buyer_name="Alpha Trade",
    )
    beta_january = _create_invoice(
        headers,
        issue_date="2091-01-20",
        buyer_name="Beta Services",
    )
    payment = client.post(
        f"/invoices/{beta_january['id']}/payment",
        headers=headers,
        json={
            "payment_date": beta_january["issue_date"],
            "account": "bank",
        },
    )
    assert payment.status_code == 201, payment.text

    january = client.get(
        "/invoices/list",
        headers=headers,
        params={"year": 2091, "month": 1},
    )
    alpha = client.get(
        "/invoices/list",
        headers=headers,
        params={"buyer_query": "alpha"},
    )
    date_range = client.get(
        "/invoices/list",
        headers=headers,
        params={"date_from": "2091-01-15", "date_to": "2091-01-31"},
    )
    unpaid = client.get(
        "/invoices/list",
        headers=headers,
        params={"unpaid_only": True},
    )
    combined = client.get(
        "/invoices/list",
        headers=headers,
        params={
            "year": 2091,
            "month": 1,
            "buyer_query": "alpha",
            "unpaid_only": True,
            "date_from": "2091-01-01",
            "date_to": "2091-01-31",
        },
    )

    for response in (january, alpha, date_range, unpaid, combined):
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(response.json()["items"])

    assert {item["id"] for item in january.json()["items"]} == {
        alpha_january["id"],
        beta_january["id"],
    }
    assert {item["id"] for item in alpha.json()["items"]} == {
        alpha_january["id"],
        alpha_february["id"],
    }
    assert [item["id"] for item in date_range.json()["items"]] == [
        beta_january["id"]
    ]
    assert {item["id"] for item in unpaid.json()["items"]} == {
        alpha_january["id"],
        alpha_february["id"],
    }
    assert [item["id"] for item in combined.json()["items"]] == [
        alpha_january["id"]
    ]


def test_detail_contract_and_tenant_isolation() -> None:
    owner = _headers("detail-owner")
    other = _headers("detail-other")
    created = _create_invoice(owner, item_count=2)
    missing_id = created["id"] + 1_000_000_000

    detail = client.get(f"/invoices/{created['id']}", headers=owner)
    missing = client.get(f"/invoices/{missing_id}", headers=owner)
    cross_tenant = client.get(f"/invoices/{created['id']}", headers=other)
    missing_header = client.get(f"/invoices/{created['id']}")

    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == created["id"]
    assert detail.json()["invoice_number"] == created["invoice_number"]
    assert len(detail.json()["items"]) == 2
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Invoice not found"}
    assert cross_tenant.status_code == 404
    assert cross_tenant.json() == {"detail": "Invoice not found"}
    assert missing_header.status_code == 400


def test_payment_is_visible_duplicate_rejected_and_tenant_scoped() -> None:
    owner = _headers("paid-owner")
    other = _headers("paid-other")
    created = _create_invoice(owner)
    invoice_id = created["id"]
    missing_id = invoice_id + 1_000_000_000
    payload = {
        "payment_date": created["issue_date"],
        "account": "bank",
    }

    first = client.post(
        f"/invoices/{invoice_id}/payment",
        headers=owner,
        json=payload,
    )
    second = client.post(
        f"/invoices/{invoice_id}/payment",
        headers=owner,
        json=payload,
    )
    detail = client.get(f"/invoices/{invoice_id}", headers=owner)
    listed = client.get("/invoices/list", headers=owner)
    cross_tenant = client.post(
        f"/invoices/{invoice_id}/payment",
        headers=other,
        json=payload,
    )
    missing = client.post(
        f"/invoices/{missing_id}/payment",
        headers=owner,
        json=payload,
    )
    missing_header = client.post(
        f"/invoices/{invoice_id}/payment",
        json=payload,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json() == {"detail": "Invoice payment already exists"}
    assert detail.status_code == 200
    assert detail.json()["is_paid"] is True
    listed_row = next(
        item for item in listed.json()["items"] if item["id"] == invoice_id
    )
    assert listed_row["is_paid"] is True
    assert cross_tenant.status_code == 404
    assert cross_tenant.json() == {"detail": "Invoice not found"}
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Invoice not found"}
    assert missing_header.status_code == 400


def test_delete_removes_invoice_and_items_and_preserves_tenant_isolation() -> None:
    owner = _headers("delete-owner")
    other = _headers("delete-other")
    created = _create_invoice(owner, item_count=2)
    invoice_id = created["id"]
    item_ids = {item["id"] for item in created["items"]}
    missing_id = invoice_id + 1_000_000_000

    cross_tenant = client.delete(f"/invoices/{invoice_id}", headers=other)
    missing = client.delete(f"/invoices/{missing_id}", headers=owner)
    missing_header = client.delete(f"/invoices/{invoice_id}")
    deleted = client.delete(f"/invoices/{invoice_id}", headers=owner)
    detail_after = client.get(f"/invoices/{invoice_id}", headers=owner)
    list_after = client.get("/invoices/list", headers=owner)

    assert cross_tenant.status_code == 404
    assert cross_tenant.json() == {"detail": "Invoice not found"}
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Invoice not found"}
    assert missing_header.status_code == 400
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert detail_after.status_code == 404
    assert all(
        item["id"] != invoice_id for item in list_after.json()["items"]
    )

    with SessionLocal() as db:
        remaining_item_ids = {
            item_id
            for (item_id,) in (
                db.query(InvoiceItem.id)
                .filter(InvoiceItem.id.in_(item_ids))
                .all()
            )
        }
    assert remaining_item_ids == set()


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 201},
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"year": 1899},
        {"month": 13},
        {"date_from": "not-a-date"},
        {"date_to": "2091-99-99"},
    ],
)
def test_list_rejects_invalid_query_parameters(params: dict) -> None:
    headers = _headers("validation")

    response = client.get("/invoices/list", headers=headers, params=params)

    assert response.status_code == 422
