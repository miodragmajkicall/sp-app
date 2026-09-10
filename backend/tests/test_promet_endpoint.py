from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    CashEntry,
    Invoice,
    Tenant,
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
)


def _create_tenant(
    client: TestClient,
    prefix: str,
) -> str:
    code = f"{prefix}-{uuid4().hex[:8]}"
    response = client.post(
        "/tenants",
        json={"code": code, "name": prefix},
    )
    assert response.status_code == 201, response.text
    return code


def _add_tax_profile(
    db,
    *,
    tenant_code: str,
    entity: str,
    regime: str,
    scenario_key: str,
) -> None:
    db.add(
        TenantTaxProfileSettings(
            tenant_code=tenant_code,
            entity=entity,
            regime=regime,
            scenario_key=scenario_key,
            has_additional_activity=False,
        )
    )
    db.flush()


def _add_invoice(
    db,
    *,
    tenant_code: str,
    invoice_number: str,
    buyer_name: str,
) -> Invoice:
    invoice = Invoice(
        tenant_code=tenant_code,
        invoice_number=invoice_number,
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        buyer_name=buyer_name,
        buyer_type="BUSINESS",
        buyer_tax_id="4400000000000",
        total_base=Decimal("100.00"),
        total_vat=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        is_paid=True,
    )
    db.add(invoice)
    db.flush()
    return invoice


def _add_cash(
    db,
    *,
    tenant_code: str,
    entry_date: date,
    kind: str,
    amount: str,
    account: str,
    recognition_class: str | None,
    invoice_id: int | None = None,
    description: str | None = None,
) -> CashEntry:
    row = CashEntry(
        tenant_code=tenant_code,
        entry_date=entry_date,
        kind=kind,
        amount=Decimal(amount),
        account=account,
        recognition_class=recognition_class,
        tax_treatment=None,
        invoice_id=invoice_id,
        input_invoice_id=None,
        description=description,
    )
    db.add(row)
    db.flush()
    return row


def test_promet_rs_uses_canonical_dataset() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-rs")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

        invoice = _add_invoice(
            db,
            tenant_code=tenant_code,
            invoice_number="PR-END-001",
            buyer_name="Canonical Kupac",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="100.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Plaćeno preko banke",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 11),
            kind="income",
            amount="25.00",
            account="cash",
            recognition_class="business_activity",
            description="Ručni poslovni prihod",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 12),
            kind="income",
            amount="50.00",
            account="cash",
            recognition_class="cash_only",
            description="Samo novčani tok",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 13),
            kind="expense",
            amount="40.00",
            account="bank",
            recognition_class="business_activity",
            description="Rashod ne pripada ovoj knjizi",
        )

        db.commit()

        response = client.get(
            "/promet",
            headers={"X-Tenant-Code": tenant_code},
        )

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["total"] == 2
        assert len(body["items"]) == 2

        # UI contract ostaje newest-first.
        assert body["items"][0]["date"] == "2026-09-11"
        assert body["items"][0]["document_number"] is None
        assert body["items"][0]["partner_name"] == "Ručni poslovni prihod"
        assert Decimal(body["items"][0]["amount"]) == Decimal("25.00")

        assert body["items"][1]["date"] == "2026-09-10"
        assert body["items"][1]["document_number"] == "PR-END-001"
        assert body["items"][1]["partner_name"] == "Canonical Kupac"
        assert Decimal(body["items"][1]["amount"]) == Decimal("100.00")

        # total == 2 i konkretna dva reda iznad zaključavaju
        # da sama Invoice ne proizvodi dodatni canonical događaj.
    finally:
        db.close()


def test_promet_filters_partner_description_and_paginates_after_filtering() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-filter")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 8, 31),
            kind="income",
            amount="10.00",
            account="cash",
            recognition_class="business_activity",
            description="Stari prihod",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="20.00",
            account="cash",
            recognition_class="business_activity",
            description="Alpha usluga",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 2),
            kind="income",
            amount="30.00",
            account="bank",
            recognition_class="business_activity",
            description="Alpha druga usluga",
        )
        db.commit()

        response = client.get(
            "/promet",
            headers={"X-Tenant-Code": tenant_code},
            params={
                "year": 2026,
                "month": 9,
                "partner_query": "ALPHA",
                "limit": 1,
                "offset": 1,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["total"] == 2
        assert len(body["items"]) == 1
        assert body["items"][0]["date"] == "2026-09-01"
        assert body["items"][0]["partner_name"] == "Alpha usluga"
    finally:
        db.close()


def test_promet_missing_configuration_fails_closed_without_creating_profiles() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-unconfigured")

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "promet_needs_configuration"
    assert detail["reason_code"] == "unsupported_or_missing_entity"
    assert detail["blocking_fields"] == ["entity"]

    db = SessionLocal()
    try:
        tax_profile = db.execute(
            select(TenantTaxProfileSettings).where(
                TenantTaxProfileSettings.tenant_code == tenant_code
            )
        ).scalar_one_or_none()

        business_profile = db.execute(
            select(TenantBusinessProfileSettings).where(
                TenantBusinessProfileSettings.tenant_code == tenant_code
            )
        ).scalar_one_or_none()

        assert tax_profile is None
        assert business_profile is None
    finally:
        db.close()


def test_promet_unknown_tenant_returns_404_without_creating_it() -> None:
    client = TestClient(app)
    tenant_code = f"promet-missing-{uuid4().hex[:8]}"

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"

    db = SessionLocal()
    try:
        stored = db.execute(
            select(Tenant).where(Tenant.code == tenant_code)
        ).scalar_one_or_none()
        assert stored is None
    finally:
        db.close()


def test_promet_not_applicable_mode_fails_closed() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-not-applicable")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="books",
            scenario_key="rs_primary",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "promet_not_applicable",
        "reason_code": "rs_books_promet_not_applicable",
    }


def test_promet_applicable_but_unimplemented_mode_fails_closed() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-fbih")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="FBiH",
            regime="pausal",
            scenario_key="fbih_obrt",
        )
        db.add(
            TenantBusinessProfileSettings(
                tenant_code=tenant_code,
                has_noncash_sales_to_legal_entities=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "promet_dataset_not_implemented",
        "mode": "fbih_kp1042_pausal_b2b",
    }
