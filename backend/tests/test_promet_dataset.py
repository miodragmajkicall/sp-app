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
    query_canonical_promet_page,
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

        with pytest.raises(
            UnsupportedPrometDatasetModeError,
            match="Promet dataset mode is not implemented",
        ):
            query_canonical_promet_page(
                db,
                tenant_code=tenant_code,
                mode=mode,
            )
    finally:
        db.close()


def test_rs_optimized_query_paginates_deterministically_and_keeps_full_summary() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-query-page")

    db = SessionLocal()
    try:
        first = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="10.00",
            account="cash",
            recognition_class="business_activity",
            description="First",
        )
        second = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="20.00",
            account="bank",
            recognition_class="business_activity",
            description="Second",
        )
        third = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="30.00",
            account="cash",
            recognition_class="business_activity",
            description="Third",
        )
        db.commit()

        page_one = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            limit=2,
            offset=0,
        )

        assert page_one.total == 3
        assert page_one.total_amount == Decimal("60.00")
        assert page_one.cash_amount == Decimal("40.00")
        assert page_one.bank_amount == Decimal("20.00")
        assert [event.source_id for event in page_one.items] == [
            third.id,
            second.id,
        ]

        page_two = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            limit=2,
            offset=2,
        )

        assert page_two.total == 3
        assert page_two.total_amount == Decimal("60.00")
        assert page_two.cash_amount == Decimal("40.00")
        assert page_two.bank_amount == Decimal("20.00")
        assert [event.source_id for event in page_two.items] == [
            first.id,
        ]

        past_end = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            limit=2,
            offset=99,
        )

        assert past_end.total == 3
        assert past_end.total_amount == Decimal("60.00")
        assert past_end.cash_amount == Decimal("40.00")
        assert past_end.bank_amount == Decimal("20.00")
        assert past_end.items == ()
    finally:
        db.close()


def test_rs_optimized_query_applies_month_and_date_filters() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-query-filters")

    db = SessionLocal()
    try:
        old_september = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2025, 9, 20),
            kind="income",
            amount="5.00",
            account="cash",
            recognition_class="business_activity",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 8, 31),
            kind="income",
            amount="10.00",
            account="cash",
            recognition_class="business_activity",
        )
        september_first = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="20.00",
            account="cash",
            recognition_class="business_activity",
        )
        september_middle = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 15),
            kind="income",
            amount="30.00",
            account="bank",
            recognition_class="business_activity",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 10, 1),
            kind="income",
            amount="40.00",
            account="bank",
            recognition_class="business_activity",
        )
        db.commit()

        month_only = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            month=9,
            limit=20,
        )

        assert month_only.total == 3
        assert month_only.total_amount == Decimal("55.00")
        assert [event.source_id for event in month_only.items] == [
            september_middle.id,
            september_first.id,
            old_september.id,
        ]

        intersection = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            year=2026,
            month=9,
            date_from=date(2026, 9, 10),
            date_to=date(2026, 9, 30),
            limit=20,
        )

        assert intersection.total == 1
        assert intersection.total_amount == Decimal("30.00")
        assert intersection.cash_amount == Decimal("0.00")
        assert intersection.bank_amount == Decimal("30.00")
        assert [event.source_id for event in intersection.items] == [
            september_middle.id,
        ]
    finally:
        db.close()


def test_rs_optimized_query_does_not_hide_invalid_source_outside_filters_or_page() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-query-invalid")

    db = SessionLocal()
    try:
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2025, 1, 1),
            kind="income",
            amount="0.00",
            account="cash",
            recognition_class="business_activity",
            description="Invalid outside requested year",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="100.00",
            account="bank",
            recognition_class="business_activity",
            description="Valid requested row",
        )

        db.commit()

        with pytest.raises(
            RuntimeError,
            match="Promet income source must have a positive amount",
        ):
            query_canonical_promet_page(
                db,
                tenant_code=tenant_code,
                mode=PrometMode.RS_SMALL_ENTREPRENEUR,
                year=2026,
                limit=1,
                offset=0,
            )
    finally:
        db.close()



def test_rs_optimized_query_date_scope_excludes_invalid_before_validation() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-query-date-scope")

    db = SessionLocal()
    try:
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2025, 1, 1),
            kind="income",
            amount="0.00",
            account="cash",
            recognition_class="business_activity",
            description="Invalid outside date scope",
        )

        valid = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="125.00",
            account="bank",
            recognition_class="business_activity",
            description="Valid inside date scope",
        )

        db.commit()

        events = list_canonical_promet_events(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )

        page = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            year=2026,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            limit=20,
        )

        assert [event.source_id for event in events] == [valid.id]
        assert page.total == 1
        assert page.total_amount == Decimal("125.00")
        assert page.cash_amount == Decimal("0.00")
        assert page.bank_amount == Decimal("125.00")
        assert [event.source_id for event in page.items] == [valid.id]
    finally:
        db.close()


def test_rs_optimized_query_preserves_linked_invoice_traceability() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-query-linked")

    db = SessionLocal()
    try:
        invoice = _add_invoice(
            db,
            tenant_code=tenant_code,
            invoice_number="OPT-PR-001",
            buyer_name="Optimizovani Kupac",
            buyer_type="BUSINESS",
            buyer_tax_id="4400000000000",
            amount="175.00",
        )

        payment = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 12),
            kind="income",
            amount="175.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Optimized linked payment",
        )

        db.commit()

        page = query_canonical_promet_page(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            limit=20,
        )

        assert page.total == 1
        assert page.total_amount == Decimal("175.00")
        assert len(page.items) == 1

        event = page.items[0]

        assert event.source_id == payment.id
        assert event.source_type is PrometSourceType.OUTGOING_INVOICE_PAYMENT
        assert event.source_document_id == invoice.id
        assert event.document_number == "OPT-PR-001"
        assert event.counterparty_name == "Optimizovani Kupac"
        assert event.counterparty_type == "BUSINESS"
        assert event.counterparty_tax_id == "4400000000000"
        assert event.payment_channel == "bank"
        assert event.amount == Decimal("175.00")
        assert event.description == "Optimized linked payment"
    finally:
        db.close()


def test_rs_optimized_query_rejects_cross_tenant_invoice_link() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-query-local")
    foreign_tenant = _create_tenant(client, "promet-query-foreign")

    db = SessionLocal()
    try:
        foreign_invoice = _add_invoice(
            db,
            tenant_code=foreign_tenant,
            invoice_number="FOREIGN-PR-001",
            buyer_name="Foreign buyer",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 15),
            kind="income",
            amount="100.00",
            account="bank",
            recognition_class=None,
            invoice_id=foreign_invoice.id,
            description="Cross-tenant invoice reference",
        )

        db.commit()

        with pytest.raises(
            RuntimeError,
            match=(
                "Outgoing invoice payment points to an unavailable "
                "invoice for this tenant"
            ),
        ):
            list_canonical_promet_events(
                db,
                tenant_code=tenant_code,
                mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            )

        with pytest.raises(
            RuntimeError,
            match=(
                "Outgoing invoice payment points to an unavailable "
                "invoice for this tenant"
            ),
        ):
            query_canonical_promet_page(
                db,
                tenant_code=tenant_code,
                mode=PrometMode.RS_SMALL_ENTREPRENEUR,
                limit=20,
            )
    finally:
        db.close()
