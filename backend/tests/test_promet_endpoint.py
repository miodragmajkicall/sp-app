from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
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
            effective_from=date(2025, 1, 1),
            effective_to=None,
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
        assert body["summary"] == {
            "total_amount": "125.00",
            "cash_amount": "25.00",
            "bank_amount": "100.00",
        }
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
        assert body["summary"] == {
            "total_amount": "50.00",
            "cash_amount": "20.00",
            "bank_amount": "30.00",
        }
        assert len(body["items"]) == 1
        assert body["items"][0]["date"] == "2026-09-01"
        assert body["items"][0]["partner_name"] == "Alpha usluga"
    finally:
        db.close()


@pytest.mark.parametrize(
    "pagination,partner_params",
    [
        ({"limit": 1, "offset": 1}, {}),
        ({"limit": 1, "offset": 1}, {"partner_query": "   "}),
        ({"page": 2, "page_size": 1, "limit": 2, "offset": 0}, {}),
    ],
    ids=["limit-offset", "whitespace-partner", "page-priority"],
)
def test_promet_optimized_path_paginates_with_full_filtered_summary(
    monkeypatch: pytest.MonkeyPatch,
    pagination: dict,
    partner_params: dict,
) -> None:
    from app.routes import promet as promet_routes

    def unexpected_fallback(*args, **kwargs):
        pytest.fail("Expected optimized Promet query, not Python collector")

    monkeypatch.setattr(
        promet_routes, "list_canonical_promet_events", unexpected_fallback
    )
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-optimized")
    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )
        for entry_date, amount, account in [
            (date(2025, 9, 11), "100.00", "cash"),
            (date(2026, 8, 11), "200.00", "bank"),
            (date(2026, 9, 1), "300.00", "cash"),
            (date(2026, 9, 10), "10.00", "cash"),
            (date(2026, 9, 11), "20.00", "bank"),
            (date(2026, 9, 12), "30.00", "cash"),
            (date(2026, 9, 30), "400.00", "bank"),
        ]:
            _add_cash(
                db,
                tenant_code=tenant_code,
                entry_date=entry_date,
                kind="income",
                amount=amount,
                account=account,
                recognition_class="business_activity",
                description="Poslovni prihod",
            )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
        params={
            "year": 2026,
            "month": 9,
            "date_from": "2026-09-10",
            "date_to": "2026-09-12",
            **pagination,
            **partner_params,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["summary"] == {
        "total_amount": "60.00",
        "cash_amount": "40.00",
        "bank_amount": "20.00",
    }
    assert len(body["items"]) == 1
    assert body["items"][0]["date"] == "2026-09-11"
    assert Decimal(body["items"][0]["amount"]) == Decimal("20.00")


@pytest.mark.parametrize("partner_query", ["%", "_", " STRASSE "])
def test_promet_partner_query_is_literal_casefold_substring(
    monkeypatch: pytest.MonkeyPatch,
    partner_query: str,
) -> None:
    from app.routes import promet as promet_routes

    def unexpected_optimized_query(*args, **kwargs):
        pytest.fail("Expected Python partner filtering, not optimized query")

    monkeypatch.setattr(
        promet_routes, "query_canonical_promet_page", unexpected_optimized_query
    )
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-literal")
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
            invoice_number="PR-LITERAL-001",
            buyer_name="Straße%_ Kupac",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="10.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Uplata fakture",
        )
        for day, description, amount in [
            (11, "Straße%_ usluga", "20.00"),
            (12, "Drugi kupac", "90.00"),
        ]:
            _add_cash(
                db,
                tenant_code=tenant_code,
                entry_date=date(2026, 9, day),
                kind="income",
                amount=amount,
                account="cash",
                recognition_class="business_activity",
                description=description,
            )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
        params={"partner_query": partner_query},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["summary"] == {
        "total_amount": "30.00",
        "cash_amount": "20.00",
        "bank_amount": "10.00",
    }
    assert [item["partner_name"] for item in body["items"]] == [
        "Straße%_ usluga",
        "Straße%_ Kupac",
    ]


def test_promet_empty_filtered_result_returns_zero_summary() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-endpoint-empty-summary")

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
            entry_date=date(2026, 9, 1),
            kind="income",
            amount="12.34",
            account="cash",
            recognition_class="business_activity",
            description="Septembarski prihod",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet",
        headers={"X-Tenant-Code": tenant_code},
        params={"year": 2025},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "total": 0,
        "summary": {
            "total_amount": "0.00",
            "cash_amount": "0.00",
            "bank_amount": "0.00",
        },
        "items": [],
    }


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

def test_promet_csv_export_uses_canonical_dataset_tenant_isolation_and_asc_order() -> None:
    import csv
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-csv-canonical")
    other_tenant = _create_tenant(client, "promet-csv-other")

    db = SessionLocal()
    try:
        for code in (tenant_code, other_tenant):
            _add_tax_profile(
                db,
                tenant_code=code,
                entity="RS",
                regime="two_percent",
                scenario_key="rs_primary",
            )

        invoice = _add_invoice(
            db,
            tenant_code=tenant_code,
            invoice_number="PR-CSV-001",
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
            description="Uplata fakture",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 9),
            kind="income",
            amount="25.00",
            account="cash",
            recognition_class="business_activity",
            description="Rani ručni prihod",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="30.00",
            account="cash",
            recognition_class="business_activity",
            description="Kasniji isti datum",
        )

        # Canonical Promet export mora isključiti ova dva reda.
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 8),
            kind="income",
            amount="50.00",
            account="cash",
            recognition_class="cash_only",
            description="Samo novčani tok",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 7),
            kind="expense",
            amount="40.00",
            account="bank",
            recognition_class="business_activity",
            description="Rashod ne pripada ovoj knjizi",
        )

        # Eksplicitni tenant-isolation dokaz.
        _add_cash(
            db,
            tenant_code=other_tenant,
            entry_date=date(2026, 9, 6),
            kind="income",
            amount="999.00",
            account="cash",
            recognition_class="business_activity",
            description="Drugi tenant",
        )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="promet-export.csv"'
    )
    assert response.content.startswith(b"\xef\xbb\xbf")

    rows = list(
        csv.reader(
            StringIO(
                response.content.decode("utf-8-sig"),
                newline="",
            ),
            delimiter=";",
        )
    )

    # Export je hronološki ASC; isti datum koristi source_id ASC.
    # Manual canonical prihod nema sintetički CE-* dokument.
    assert rows == [
        ["Datum", "Broj dokumenta", "Partner", "Iznos", "Napomena"],
        ["2026-09-09", "", "Rani ručni prihod", "25.00", ""],
        [
            "2026-09-10",
            "PR-CSV-001",
            "Canonical Kupac",
            "100.00",
            "Uplata fakture",
        ],
        ["2026-09-10", "", "Kasniji isti datum", "30.00", ""],
    ]


def test_promet_csv_export_applies_all_date_filters() -> None:
    import csv
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-csv-dates")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

        for event_date, description in (
            (date(2026, 8, 31), "Avgust"),
            (date(2026, 9, 1), "Septembar prvi"),
            (date(2026, 9, 2), "Septembar drugi"),
            (date(2026, 10, 1), "Oktobar"),
            (date(2025, 9, 2), "Druga godina"),
        ):
            _add_cash(
                db,
                tenant_code=tenant_code,
                entry_date=event_date,
                kind="income",
                amount="10.00",
                account="cash",
                recognition_class="business_activity",
                description=description,
            )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": tenant_code},
        params={
            "year": 2026,
            "month": 9,
            "date_from": "2026-09-02",
            "date_to": "2026-09-30",
        },
    )

    assert response.status_code == 200, response.text

    rows = list(
        csv.reader(
            StringIO(
                response.content.decode("utf-8-sig"),
                newline="",
            ),
            delimiter=";",
        )
    )

    assert rows == [
        ["Datum", "Broj dokumenta", "Partner", "Iznos", "Napomena"],
        ["2026-09-02", "", "Septembar drugi", "10.00", ""],
    ]


@pytest.mark.parametrize("partner_query", ["%", "_", " STRASSE "])
def test_promet_csv_export_partner_query_is_literal_casefold_substring(
    partner_query: str,
) -> None:
    import csv
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-csv-partner")

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
            invoice_number="PR-CSV-LITERAL-001",
            buyer_name="Straße%_ Kupac",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="10.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Uplata fakture",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 11),
            kind="income",
            amount="20.00",
            account="cash",
            recognition_class="business_activity",
            description="Straße%_ usluga",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 12),
            kind="income",
            amount="90.00",
            account="cash",
            recognition_class="business_activity",
            description="Drugi kupac",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": tenant_code},
        params={"partner_query": partner_query},
    )

    assert response.status_code == 200, response.text

    rows = list(
        csv.reader(
            StringIO(response.content.decode("utf-8-sig"), newline=""),
            delimiter=";",
        )
    )

    assert rows == [
        ["Datum", "Broj dokumenta", "Partner", "Iznos", "Napomena"],
        [
            "2026-09-10",
            "PR-CSV-LITERAL-001",
            "Straße%_ Kupac",
            "10.00",
            "Uplata fakture",
        ],
        ["2026-09-11", "", "Straße%_ usluga", "20.00", ""],
    ]


def test_promet_csv_export_is_not_limited_by_ui_pagination() -> None:
    import csv
    from datetime import timedelta
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-csv-full-set")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

        start = date(2026, 1, 1)
        for index in range(55):
            _add_cash(
                db,
                tenant_code=tenant_code,
                entry_date=start + timedelta(days=index),
                kind="income",
                amount="1.00",
                account="cash",
                recognition_class="business_activity",
                description=f"CSV red {index + 1:02d}",
            )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": tenant_code},
        params={"year": 2026},
    )

    assert response.status_code == 200, response.text

    rows = list(
        csv.reader(
            StringIO(response.content.decode("utf-8-sig"), newline=""),
            delimiter=";",
        )
    )

    assert len(rows) == 56
    assert rows[1][2] == "CSV red 01"
    assert rows[-1][2] == "CSV red 55"


def test_promet_csv_export_format_security_and_source_preservation() -> None:
    import csv
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-csv-security")

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
            invoice_number="=1+1",
            buyer_name=" \t+SUM(1,2)",
        )
        entry = _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 9),
            kind="income",
            amount="12.34",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="\n@SUM(1,2)",
        )

        invoice_id = invoice.id
        entry_id = entry.id
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="promet-export.csv"'
    )

    columns = [
        "Datum",
        "Broj dokumenta",
        "Partner",
        "Iznos",
        "Napomena",
    ]
    expected_row = [
        "2026-09-09",
        "\t=1+1",
        "\t \t+SUM(1,2)",
        "12.34",
        "\t\n@SUM(1,2)",
    ]

    buffer = StringIO(newline="")
    writer = csv.writer(
        buffer,
        delimiter=";",
        quoting=csv.QUOTE_ALL,
    )
    writer.writerow(columns)
    writer.writerow(expected_row)

    expected_bytes = buffer.getvalue().encode("utf-8-sig")

    assert response.content == expected_bytes
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.content.endswith(b"\r\n")

    parsed = list(
        csv.reader(
            StringIO(response.content.decode("utf-8-sig"), newline=""),
            delimiter=";",
        )
    )
    assert parsed == [columns, expected_row]

    # Export zaštita ne smije mijenjati vrijednosti spremljene u bazi.
    db = SessionLocal()
    try:
        stored_invoice = db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        ).scalar_one()
        stored_entry = db.execute(
            select(CashEntry).where(CashEntry.id == entry_id)
        ).scalar_one()

        assert stored_invoice.invoice_number == "=1+1"
        assert stored_invoice.buyer_name == " \t+SUM(1,2)"
        assert stored_entry.description == "\n@SUM(1,2)"
    finally:
        db.close()


def test_promet_csv_export_empty_result_is_header_only() -> None:
    import csv
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-csv-empty")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": tenant_code},
        params={"year": 2026},
    )

    assert response.status_code == 200, response.text

    rows = list(
        csv.reader(
            StringIO(response.content.decode("utf-8-sig"), newline=""),
            delimiter=";",
        )
    )

    assert rows == [
        ["Datum", "Broj dokumenta", "Partner", "Iznos", "Napomena"],
    ]


def test_promet_csv_export_uses_same_eligibility_guards_as_list() -> None:
    client = TestClient(app)

    missing_tenant = f"promet-csv-missing-{uuid4().hex[:8]}"
    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": missing_tenant},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"

    db = SessionLocal()
    try:
        stored = db.execute(
            select(Tenant).where(Tenant.code == missing_tenant)
        ).scalar_one_or_none()
        assert stored is None
    finally:
        db.close()

    unconfigured = _create_tenant(client, "promet-csv-unconfigured")
    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": unconfigured},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "promet_needs_configuration"

    not_applicable = _create_tenant(client, "promet-csv-not-applicable")
    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=not_applicable,
            entity="RS",
            regime="books",
            scenario_key="rs_primary",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": not_applicable},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "promet_not_applicable",
        "reason_code": "rs_books_promet_not_applicable",
    }

    unsupported = _create_tenant(client, "promet-csv-fbih")
    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=unsupported,
            entity="FBiH",
            regime="pausal",
            scenario_key="fbih_obrt",
        )
        db.add(
            TenantBusinessProfileSettings(
                tenant_code=unsupported,
                has_noncash_sales_to_legal_entities=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export",
        headers={"X-Tenant-Code": unsupported},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "promet_dataset_not_implemented",
        "mode": "fbih_kp1042_pausal_b2b",
    }


# ============================================================
# PROMET-6A — canonical PDF export
# ============================================================


def _read_promet_pdf_response(response):
    from io import BytesIO

    from pypdf import PdfReader

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")

    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )
    return reader, text


def test_promet_pdf_export_uses_canonical_dataset_and_chronological_order() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-canonical")
    other_tenant = _create_tenant(client, "promet-pdf-other")

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
            invoice_number="PR-PDF-001",
            buyer_name="Canonical Kupac",
        )

        # Rani manualni canonical prihod.
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 9),
            kind="income",
            amount="25.00",
            account="cash",
            recognition_class="business_activity",
            description="Rani ručni prihod",
        )

        # Linked outgoing invoice payment.
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="100.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Uplata fakture",
        )

        # Isti datum, kasniji canonical source_id.
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="30.00",
            account="cash",
            recognition_class="business_activity",
            description="Kasniji isti datum",
        )

        # Ne smiju ući u canonical Promet PDF.
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 11),
            kind="income",
            amount="50.00",
            account="cash",
            recognition_class="cash_only",
            description="Samo novčani tok",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 12),
            kind="expense",
            amount="40.00",
            account="bank",
            recognition_class="business_activity",
            description="Rashod ne pripada knjizi",
        )
        _add_cash(
            db,
            tenant_code=other_tenant,
            entry_date=date(2026, 9, 8),
            kind="income",
            amount="999.00",
            account="cash",
            recognition_class="business_activity",
            description="Drugi tenant",
        )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
    )

    reader, pdf_text = _read_promet_pdf_response(response)

    assert response.headers["content-disposition"] == (
        'attachment; filename="promet-export.pdf"'
    )
    assert len(reader.pages) >= 1

    assert "Knjiga prometa" in pdf_text
    assert "Informativni izvještaj - nije službeni obrazac" in pdf_text

    assert "PR-PDF-001" in pdf_text
    assert "Canonical Kupac" in pdf_text
    assert "Uplata fakture" in pdf_text
    assert "Rani ručni prihod" in pdf_text
    assert "Kasniji isti datum" in pdf_text

    # Canonical export nema legacy/sintetičku semantiku.
    assert "KP-1042" not in pdf_text
    assert "bezgotovinskog prometa" not in pdf_text
    assert "CE-" not in pdf_text
    assert "Samo novčani tok" not in pdf_text
    assert "Rashod ne pripada knjizi" not in pdf_text
    assert "Drugi tenant" not in pdf_text

    # Hronološki ASC, a isti datum razrješava canonical source_id ASC.
    assert pdf_text.index("Rani ručni prihod") < pdf_text.index("Canonical Kupac")
    assert pdf_text.index("Canonical Kupac") < pdf_text.index("Kasniji isti datum")

    assert "155.00 BAM" in pdf_text


def test_promet_pdf_export_applies_all_date_filters() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-dates")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

        for event_date, description in (
            (date(2026, 8, 31), "Avgust"),
            (date(2026, 9, 1), "Septembar prvi"),
            (date(2026, 9, 2), "Septembar drugi"),
            (date(2026, 10, 1), "Oktobar"),
            (date(2025, 9, 2), "Druga godina"),
        ):
            _add_cash(
                db,
                tenant_code=tenant_code,
                entry_date=event_date,
                kind="income",
                amount="10.00",
                account="cash",
                recognition_class="business_activity",
                description=description,
            )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
        params={
            "year": 2026,
            "month": 9,
            "date_from": "2026-09-02",
            "date_to": "2026-09-30",
        },
    )

    _, pdf_text = _read_promet_pdf_response(response)

    assert "Septembar drugi" in pdf_text
    assert "Avgust" not in pdf_text
    assert "Septembar prvi" not in pdf_text
    assert "Oktobar" not in pdf_text
    assert "Druga godina" not in pdf_text
    assert "10.00 BAM" in pdf_text


@pytest.mark.parametrize("partner_query", ["%", "_", " STRASSE "])
def test_promet_pdf_export_partner_query_is_literal_casefold_substring(
    partner_query: str,
) -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-partner")

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
            invoice_number="PR-PDF-LITERAL-001",
            buyer_name="Straße%_ Kupac",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            kind="income",
            amount="10.00",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description="Uplata fakture",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 11),
            kind="income",
            amount="20.00",
            account="cash",
            recognition_class="business_activity",
            description="Straße%_ usluga",
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 12),
            kind="income",
            amount="90.00",
            account="cash",
            recognition_class="business_activity",
            description="Drugi kupac",
        )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
        params={"partner_query": partner_query},
    )

    _, pdf_text = _read_promet_pdf_response(response)

    assert "Straße%_ Kupac" in pdf_text
    assert "Straße%_ usluga" in pdf_text
    assert "Drugi kupac" not in pdf_text
    assert "30.00 BAM" in pdf_text


def test_promet_pdf_export_is_not_limited_by_ui_pagination() -> None:
    from datetime import timedelta

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-full-set")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

        start = date(2026, 1, 1)
        for index in range(55):
            _add_cash(
                db,
                tenant_code=tenant_code,
                entry_date=start + timedelta(days=index),
                kind="income",
                amount="1.00",
                account="cash",
                recognition_class="business_activity",
                description=f"PDF red {index + 1:02d}",
            )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
        params={"year": 2026},
    )

    reader, pdf_text = _read_promet_pdf_response(response)

    assert len(reader.pages) >= 2
    assert "PDF red 01" in pdf_text
    assert "PDF red 55" in pdf_text
    assert pdf_text.index("PDF red 01") < pdf_text.index("PDF red 55")
    assert "55.00 BAM" in pdf_text


def test_promet_pdf_export_empty_result_is_valid_pdf() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-empty")

    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=tenant_code,
            entity="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
        params={"year": 2028},
    )

    _, pdf_text = _read_promet_pdf_response(response)

    assert "Knjiga prometa" in pdf_text
    assert "Nema evidentiranih stavki za odabrani period." in pdf_text
    assert "0.00 BAM" in pdf_text


def test_promet_pdf_export_uses_same_eligibility_guards_as_list() -> None:
    client = TestClient(app)

    missing_tenant = f"promet-pdf-missing-{uuid4().hex[:8]}"
    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": missing_tenant},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"

    unconfigured = _create_tenant(client, "promet-pdf-unconfigured")
    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": unconfigured},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "promet_needs_configuration"

    not_applicable = _create_tenant(client, "promet-pdf-not-applicable")
    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=not_applicable,
            entity="RS",
            regime="books",
            scenario_key="rs_primary",
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": not_applicable},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "promet_not_applicable",
        "reason_code": "rs_books_promet_not_applicable",
    }

    unsupported = _create_tenant(client, "promet-pdf-fbih")
    db = SessionLocal()
    try:
        _add_tax_profile(
            db,
            tenant_code=unsupported,
            entity="FBiH",
            regime="pausal",
            scenario_key="fbih_obrt",
        )
        db.add(
            TenantBusinessProfileSettings(
                tenant_code=unsupported,
                has_noncash_sales_to_legal_entities=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": unsupported},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "promet_dataset_not_implemented",
        "mode": "fbih_kp1042_pausal_b2b",
    }


def test_promet_pdf_export_preserves_unicode_and_long_text() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-text")

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
            invoice_number="DUGI-DOKUMENT-BROJ-ZAVRSNI_TOKEN",
            buyer_name=(
                "Željeznička poslovna organizacija sa dugim nazivom "
                "PARTNER_ZAVRSNI_TOKEN"
            ),
        )
        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 14),
            kind="income",
            amount="123.45",
            account="bank",
            recognition_class=None,
            invoice_id=invoice.id,
            description=(
                "Dugačka napomena sa čćšđž znakovima i završetkom "
                "NAPOMENA_ZAVRSNI_TOKEN"
            ),
        )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
    )

    _, pdf_text = _read_promet_pdf_response(response)

    assert "Željeznička" in pdf_text
    assert "čćšđž" in pdf_text
    # PDF layout smije prelomiti dugačak broj dokumenta preko više linija.
    # Uklanjamo samo layout whitespace kako bismo dokazali da vrijednost
    # nije skraćena niti izgubljena.
    pdf_text_without_layout_whitespace = "".join(pdf_text.split())

    assert (
        "DUGI-DOKUMENT-BROJ-ZAVRSNI_TOKEN"
        in pdf_text_without_layout_whitespace
    )
    assert "PARTNER_ZAVRSNI_TOKEN" in pdf_text
    assert "NAPOMENA_ZAVRSNI_TOKEN" in pdf_text


def test_promet_pdf_unsupported_glyph_returns_422() -> None:
    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-pdf-glyph")

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
            entry_date=date(2026, 9, 14),
            kind="income",
            amount="10.00",
            account="cash",
            recognition_class="business_activity",
            description="Nepodržani znak 😀",
        )

        db.commit()
    finally:
        db.close()

    response = client.get(
        "/promet/export-pdf",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Promet PDF cannot be generated because the document contains "
        "characters unsupported by the PDF font"
    )


# ============================================================
# PROMET-FINAL-1 — semantički prazan manual description
# ============================================================


def test_promet_blank_manual_description_is_normalized_across_list_csv_pdf() -> None:
    import csv
    from decimal import Decimal
    from io import StringIO

    client = TestClient(app)
    tenant_code = _create_tenant(client, "promet-blank-description")

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
            entry_date=date(2026, 9, 14),
            kind="income",
            amount="11.00",
            account="cash",
            recognition_class="business_activity",
            description="",
        )

        _add_cash(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 15),
            kind="income",
            amount="12.00",
            account="bank",
            recognition_class="business_activity",
            description="   ",
        )

        db.commit()
    finally:
        db.close()

    headers = {"X-Tenant-Code": tenant_code}

    # LIST — oba događaja ostaju u Prometu, ali prazni UI tekst postaje None.
    response = client.get(
        "/promet",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["total"] == 2
    assert Decimal(str(payload["summary"]["total_amount"])) == Decimal("23.00")

    assert len(payload["items"]) == 2

    for item in payload["items"]:
        assert item["document_number"] is None
        assert item["partner_name"] is None
        assert item["note"] is None

    assert {
        Decimal(str(item["amount"]))
        for item in payload["items"]
    } == {
        Decimal("11.00"),
        Decimal("12.00"),
    }

    # CSV — događaji ostaju prisutni; prazna tekstualna polja ostaju prazna.
    response = client.get(
        "/promet/export",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    csv_rows = list(
        csv.reader(
            StringIO(response.content.decode("utf-8-sig")),
            delimiter=";",
        )
    )

    assert csv_rows[0] == [
        "Datum",
        "Broj dokumenta",
        "Partner",
        "Iznos",
        "Napomena",
    ]
    assert len(csv_rows) == 3

    for row in csv_rows[1:]:
        assert row[1] == ""
        assert row[2] == ""
        assert row[4] == ""

    assert {row[3] for row in csv_rows[1:]} == {"11.00", "12.00"}

    # PDF — isti canonical događaji i isti zbir, bez validacione greške.
    response = client.get(
        "/promet/export-pdf",
        headers=headers,
    )

    _, pdf_text = _read_promet_pdf_response(response)

    assert "23.00 BAM" in pdf_text
