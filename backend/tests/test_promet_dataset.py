from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import CashEntry, Invoice
from app.services.promet_dataset import (
    PrometSourceType,
    UnsupportedPrometDatasetModeError,
    list_canonical_promet_events,
)
from app.services.promet_eligibility import PrometMode


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


def _add_invoice(
    db,
    *,
    tenant_code: str,
    invoice_number: str,
    buyer_name: str,
    buyer_type: str = "BUSINESS",
    buyer_tax_id: str | None = "4400000000000",
    amount: str = "100.00",
) -> Invoice:
    invoice = Invoice(
        tenant_code=tenant_code,
        invoice_number=invoice_number,
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        buyer_name=buyer_name,
        buyer_type=buyer_type,
        buyer_tax_id=buyer_tax_id,
        total_base=Decimal(amount),
        total_vat=Decimal("0.00"),
        total_amount=Decimal(amount),
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
    input_invoice_id: int | None = None,
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
        input_invoice_id=input_invoice_id,
        description=description,
    )
    db.add(row)
    db.flush()
    return row


def test_rs_collector_includes_linked_invoice_payments_with_traceability() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-rs-linked")

    db = SessionLocal()
    try:
        cash_invoice = _add_invoice(
            db,
            tenant_code=tenant_code,
            invoice_number="PR-001",
            buyer_name="Kupac Cash",
        )
        bank_invoice = _add_invoice(
            db,
            tenant_code=tenant_code,
            invoice_number="PR-002",
            buyer_name="Kupac Bank",
        )

        cash_payment = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 5),
            kind="income",
            amount="100.00",
            account="cash",
            recognition_class=None,
            invoice_id=cash_invoice.id,
            description="Gotovinska naplata",
        )
        bank_payment = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 6),
            kind="income",
            amount="100.00",
            account="bank",
            recognition_class=None,
            invoice_id=bank_invoice.id,
            description="Bankovna naplata",
        )
        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
        )

        assert [event.source_id for event in events] == [
            cash_payment.id,
            bank_payment.id,
        ]

        first = events[0]
        assert (
            first.source_type
            is PrometSourceType.OUTGOING_INVOICE_PAYMENT
        )
        assert first.source_document_id == cash_invoice.id
        assert first.document_number == "PR-001"
        assert first.counterparty_name == "Kupac Cash"
        assert first.counterparty_type == "BUSINESS"
        assert first.counterparty_tax_id == "4400000000000"
        assert first.payment_channel == "cash"
        assert first.amount == Decimal("100.00")

        second = events[1]
        assert second.source_document_id == bank_invoice.id
        assert second.document_number == "PR-002"
        assert second.payment_channel == "bank"
    finally:
        db.close()


def test_rs_linked_invoice_payment_produces_exactly_one_canonical_event() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-rs-no-duplicate")

    db = SessionLocal()
    try:
        invoice = _add_invoice(
            db,
            tenant_code=tenant_code,
            invoice_number="PR-DUP-001",
            buyer_name="Kupac Bez Duplikata",
        )

        payment = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 8),
            kind="income",
            amount="100.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Linked payment",
        )
        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
        )

        assert len(events) == 1
        event = events[0]
        assert event.source_id == payment.id
        assert (
            event.source_type
            is PrometSourceType.OUTGOING_INVOICE_PAYMENT
        )
        assert event.source_document_id == invoice.id
        assert event.document_number == "PR-DUP-001"
    finally:
        db.close()



def test_rs_collector_includes_manual_business_income_without_fake_document() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-rs-manual")

    db = SessionLocal()
    try:
        manual = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 7),
            kind="income",
            amount="25.00",
            account="cash",
            recognition_class="business_activity",
            description="Dodatni poslovni prihod",
        )
        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
        )

        assert len(events) == 1
        event = events[0]
        assert event.source_id == manual.id
        assert event.source_type is PrometSourceType.MANUAL_BUSINESS_INCOME
        assert event.source_document_id is None
        assert event.document_number is None
        assert event.counterparty_name is None
        assert event.amount == Decimal("25.00")
    finally:
        db.close()


def test_rs_collector_excludes_cash_only_legacy_unknown_and_expenses() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-rs-excluded")

    db = SessionLocal()
    try:
        included = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="10.00",
            account="cash",
            recognition_class="business_activity",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 2),
            kind="income",
            amount="20.00",
            account="cash",
            recognition_class="cash_only",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 3),
            kind="income",
            amount="30.00",
            account="bank",
            recognition_class=None,
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 4),
            kind="expense",
            amount="40.00",
            account="bank",
            recognition_class="business_activity",
        )
        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
        )

        assert [event.source_id for event in events] == [included.id]
    finally:
        db.close()


def test_rs_collector_is_tenant_isolated() -> None:
    client = TestClient(app)
    first_tenant = _create_tenant(client, "promet-rs-a")
    second_tenant = _create_tenant(client, "promet-rs-b")

    db = SessionLocal()
    try:
        first = _add_cash(
            db,
            tenant_code=first_tenant,
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="11.00",
            account="cash",
            recognition_class="business_activity",
        )
        _add_cash(
            db,
            tenant_code=second_tenant,
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="99.00",
            account="cash",
            recognition_class="business_activity",
        )
        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=first_tenant,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
        )

        assert [event.source_id for event in events] == [first.id]
    finally:
        db.close()


def test_rs_collector_filters_dates_inclusively_and_orders_deterministically() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-rs-dates")

    db = SessionLocal()
    try:
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 8, 31),
            kind="income",
            amount="1.00",
            account="cash",
            recognition_class="business_activity",
        )
        first = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="2.00",
            account="cash",
            recognition_class="business_activity",
        )
        second = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 30),
            kind="income",
            amount="3.00",
            account="bank",
            recognition_class="business_activity",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 10, 1),
            kind="income",
            amount="4.00",
            account="bank",
            recognition_class="business_activity",
        )
        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
        )

        assert [event.source_id for event in events] == [
            first.id,
            second.id,
        ]
    finally:
        db.close()


@pytest.mark.parametrize(
    "mode",
    [
        PrometMode.FBIH_KP1042_MULTI_LOCATION,
        PrometMode.FBIH_KP1042_PAUSAL_B2B,
        PrometMode.BD_KP1042_MULTI_LOCATION,
        PrometMode.BD_KP1042_PAUSAL_B2B,
    ],
)
def test_unimplemented_modes_fail_closed(
    mode: PrometMode,
) -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-unimplemented")

    db = SessionLocal()
    try:
        with pytest.raises(
            UnsupportedPrometDatasetModeError,
            match="Promet dataset mode is not implemented",
        ):
            list_canonical_promet_events(
                db,
                tenant_code=tenant_code,
                mode=mode,
            )
    finally:
        db.close()
