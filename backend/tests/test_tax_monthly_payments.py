# /home/miso/dev/sp-app/sp-app/backend/tests/test_tax_monthly_payments.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_tax_monthly_overview_returns_12_months_with_default_payment_status():
    tenant = "tax-payments-demo-a"
    headers = {"X-Tenant-Code": tenant}

    r = client.get("/tax/monthly?year=2025", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["year"] == 2025
    assert data["tenant_code"] == tenant
    assert len(data["items"]) == 12

    # po defaultu nema payment reda → unpaid
    jan = data["items"][0]
    assert jan["month"] == 1
    assert jan["is_paid"] is False
    assert jan["paid_at"] is None


def test_tax_monthly_payment_upsert_sets_and_clears_paid_at():
    tenant = "tax-payments-demo-b"
    headers = {"X-Tenant-Code": tenant}

    # set paid with explicit paid_at
    payload = {"is_paid": True, "paid_at": "2025-01-15"}
    r = client.put("/tax/monthly/2025/1/payment", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["year"] == 2025
    assert row["month"] == 1
    assert row["is_paid"] is True
    assert row["paid_at"] == "2025-01-15"

    # unset paid -> paid_at must be null
    payload = {"is_paid": False}
    r = client.put("/tax/monthly/2025/1/payment", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["is_paid"] is False
    assert row["paid_at"] is None


def test_tax_monthly_payment_is_tenant_isolated():
    tenant_a = "tax-payments-iso-a"
    tenant_b = "tax-payments-iso-b"

    headers_a = {"X-Tenant-Code": tenant_a}
    headers_b = {"X-Tenant-Code": tenant_b}

    # A marks Jan as paid
    r = client.put(
        "/tax/monthly/2025/1/payment",
        json={"is_paid": True, "paid_at": "2025-01-10"},
        headers=headers_a,
    )
    assert r.status_code == 200, r.text

    # B overview should remain unpaid
    r = client.get("/tax/monthly?year=2025", headers=headers_b)
    assert r.status_code == 200, r.text
    data_b = r.json()
    jan_b = [x for x in data_b["items"] if x["month"] == 1][0]
    assert jan_b["is_paid"] is False
    assert jan_b["paid_at"] is None
