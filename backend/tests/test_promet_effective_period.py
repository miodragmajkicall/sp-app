from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    CashEntry,
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
)


client = TestClient(app)


def _create_tenant(prefix: str) -> str:
    tenant_code = f"{prefix}-{uuid4().hex[:8]}"

    response = client.post(
        "/tenants",
        json={
            "code": tenant_code,
            "name": prefix,
        },
    )

    assert response.status_code == 201, response.text
    return tenant_code


def _headers(tenant_code: str) -> dict[str, str]:
    return {
        "X-Tenant-Code": tenant_code,
    }


def _add_tax_period(
    db,
    *,
    tenant_code: str,
    effective_from: date | None,
    effective_to: date | None,
    entity: str = "RS",
    regime: str = "two_percent",
    scenario_key: str = "rs_primary",
) -> None:
    db.add(
        TenantTaxProfileSettings(
            tenant_code=tenant_code,
            entity=entity,
            regime=regime,
            scenario_key=scenario_key,
            has_additional_activity=False,
            effective_from=effective_from,
            effective_to=effective_to,
        )
    )
    db.flush()



def _add_business_period(
    db,
    *,
    tenant_code: str,
    effective_from: date | None,
    effective_to: date | None,
    sales_locations_count: int | None = None,
    sells_to_consumers: bool | None = None,
    daily_cash_turnover_covered_elsewhere: bool | None = None,
    has_noncash_sales_to_legal_entities: bool | None = None,
) -> None:
    db.add(
        TenantBusinessProfileSettings(
            tenant_code=tenant_code,
            sales_locations_count=sales_locations_count,
            sells_to_consumers=sells_to_consumers,
            daily_cash_turnover_covered_elsewhere=(
                daily_cash_turnover_covered_elsewhere
            ),
            has_noncash_sales_to_legal_entities=(
                has_noncash_sales_to_legal_entities
            ),
            effective_from=effective_from,
            effective_to=effective_to,
        )
    )
    db.flush()


def _add_manual_income(
    db,
    *,
    tenant_code: str,
    entry_date: date,
    amount: str = "10.00",
    description: str = "Period-aware Promet prihod",
) -> None:
    db.add(
        CashEntry(
            tenant_code=tenant_code,
            entry_date=entry_date,
            kind="income",
            amount=Decimal(amount),
            account="cash",
            recognition_class="business_activity",
            tax_treatment=None,
            invoice_id=None,
            input_invoice_id=None,
            description=description,
        )
    )
    db.flush()


def _assert_coverage_missing(
    response,
    *,
    expected_from: str,
    expected_to: str,
) -> None:
    assert response.status_code == 409, response.text

    assert response.json()["detail"] == {
        "code": "promet_profile_coverage_missing",
        "from": expected_from,
        "to": expected_to,
    }


# ---------------------------------------------------------------------------
# Explicit historical scope must be verified.
# Legacy NULL/NULL is current configuration only and cannot prove year 2026.
# ---------------------------------------------------------------------------

def test_promet_explicit_year_rejects_legacy_unverified_profile() -> None:
    tenant_code = _create_tenant("promet-period-legacy-year")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=None,
            effective_to=None,
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 14),
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    _assert_coverage_missing(
        response,
        expected_from="2026-01-01",
        expected_to="2026-12-31",
    )


# ---------------------------------------------------------------------------
# Verified open period from Jan 1 covers the whole requested year.
# ---------------------------------------------------------------------------

def test_promet_explicit_year_accepts_verified_full_coverage() -> None:
    tenant_code = _create_tenant("promet-period-full-year")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=None,
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 14),
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# Same mode on both sides does not excuse a verified coverage gap.
# ---------------------------------------------------------------------------

def test_promet_gap_inside_explicit_year_fails_closed() -> None:
    tenant_code = _create_tenant("promet-period-gap-year")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 3, 31),
        )
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 5, 1),
            effective_to=None,
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    _assert_coverage_missing(
        response,
        expected_from="2026-01-01",
        expected_to="2026-12-31",
    )


# ---------------------------------------------------------------------------
# Multiple revisions are allowed when they are contiguous and resolve
# to the same Promet mode.
# ---------------------------------------------------------------------------

def test_promet_same_mode_across_contiguous_revisions_is_allowed() -> None:
    tenant_code = _create_tenant("promet-period-same-mode")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        )
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 7, 1),
            effective_to=None,
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 2, 10),
            amount="10.00",
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 8, 10),
            amount="20.00",
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2


# ---------------------------------------------------------------------------
# One request cannot silently reinterpret a year whose eligibility/mode
# changes during the requested period.
# ---------------------------------------------------------------------------

def test_promet_mode_change_inside_explicit_year_fails_closed() -> None:
    tenant_code = _create_tenant("promet-period-mode-change")

    with SessionLocal() as db:
        # Prvi period: RS books -> Promet nije applicable.
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            regime="books",
        )

        # Current period: RS two_percent -> Promet applicable.
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 7, 1),
            effective_to=None,
            regime="two_percent",
        )

        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 8, 10),
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "promet_profile_mode_changed",
        "from": "2026-01-01",
        "to": "2026-12-31",
    }


# ---------------------------------------------------------------------------
# No temporal filters -> coverage is tied to actual canonical data span,
# not to infinite history and not only to current profile.
# ---------------------------------------------------------------------------

def test_promet_unfiltered_request_detects_gap_inside_actual_data_span() -> None:
    tenant_code = _create_tenant("promet-period-data-span-gap")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 3, 31),
        )
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 5, 1),
            effective_to=None,
        )

        # Actual Promet history spans February -> June.
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 2, 10),
            amount="10.00",
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 6, 10),
            amount="20.00",
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
    )

    _assert_coverage_missing(
        response,
        expected_from="2026-02-10",
        expected_to="2026-06-10",
    )


# ---------------------------------------------------------------------------
# month=9 without year means September across years.
# The interval between those Septembers is NOT part of requested scope.
# ---------------------------------------------------------------------------

def test_promet_month_only_does_not_require_intervening_month_coverage() -> None:
    tenant_code = _create_tenant("promet-period-month-only")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2025, 9, 1),
            effective_to=date(2025, 9, 30),
        )
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 9, 1),
            effective_to=None,
        )

        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2025, 9, 10),
            amount="10.00",
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 10),
            amount="20.00",
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"month": 9},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] == 2
    assert body["summary"]["total_amount"] == "30.00"


# ---------------------------------------------------------------------------
# LIST / CSV / PDF must expose the same profile coverage error.
# Explicit year is validated even when that year contains no Promet rows.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "/promet",
        "/promet/export",
        "/promet/export-pdf",
    ],
)
def test_promet_profile_coverage_failure_is_identical_across_outputs(
    path: str,
) -> None:
    tenant_code = _create_tenant("promet-period-output-parity")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=None,
            effective_to=None,
        )
        db.commit()

    response = client.get(
        path,
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    _assert_coverage_missing(
        response,
        expected_from="2026-01-01",
        expected_to="2026-12-31",
    )


# ---------------------------------------------------------------------------
# No filters + no canonical events does not invent a historical scope.
# A valid legacy/current RS Promet configuration can return empty output.
# ---------------------------------------------------------------------------

def test_promet_unfiltered_empty_dataset_accepts_legacy_current_profile() -> None:
    tenant_code = _create_tenant("promet-period-empty-current")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=None,
            effective_to=None,
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
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



# ---------------------------------------------------------------------------
# RS Promet eligibility ne koristi Business facts.
# Korumpirana/overlapovana Business history ne smije blokirati validan
# verified RS Tax period.
# ---------------------------------------------------------------------------

def test_promet_rs_does_not_depend_on_business_profile_history() -> None:
    tenant_code = _create_tenant("promet-period-rs-business-independent")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=None,
        )

        # Namjerno overlapovani bounded Business periodi.
        # To bi business as-of selector ispravno smatrao nejednoznačnim.
        _add_business_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            sales_locations_count=1,
        )
        _add_business_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 12, 31),
            sales_locations_count=2,
        )

        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 14),
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# Dva različita NOT_APPLICABLE pravna/scenario stanja nisu ista
# periodna klasifikacija samo zato što dijele isti status.
# ---------------------------------------------------------------------------

def test_promet_not_applicable_reason_change_is_mode_change() -> None:
    tenant_code = _create_tenant("promet-period-not-applicable-change")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            entity="RS",
            regime="books",
            scenario_key="rs_primary",
        )

        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 7, 1),
            effective_to=None,
            entity="FBiH",
            regime="pausal",
            scenario_key="fbih_obrt",
        )

        _add_business_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            has_noncash_sales_to_legal_entities=False,
        )

        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "promet_profile_mode_changed",
        "from": "2026-01-01",
        "to": "2026-12-31",
    }


# ---------------------------------------------------------------------------
# year/month/date_from/date_to koriste presjek, ne cijeli mjesec/godinu.
# Verified coverage mora postojati samo nad stvarno traženim presjekom.
# ---------------------------------------------------------------------------

def test_promet_temporal_coverage_uses_filter_intersection() -> None:
    tenant_code = _create_tenant("promet-period-filter-intersection")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 9, 10),
            effective_to=None,
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=date(2026, 9, 11),
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={
            "year": 2026,
            "month": 9,
            "date_from": "2026-09-10",
            "date_to": "2026-09-12",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# Jednostrani date bound koristi stvarni canonical raspon za nedostajući kraj.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("params", "profile_from", "event_date"),
    [
        (
            {"date_from": "2026-09-10"},
            date(2026, 9, 10),
            date(2026, 9, 12),
        ),
        (
            {"date_to": "2026-09-20"},
            date(2026, 9, 10),
            date(2026, 9, 12),
        ),
    ],
    ids=["lower-bound", "upper-bound"],
)
def test_promet_one_sided_date_bound_uses_actual_canonical_span(
    params: dict[str, str],
    profile_from: date,
    event_date: date,
) -> None:
    tenant_code = _create_tenant("promet-period-one-sided")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=profile_from,
            effective_to=None,
        )
        _add_manual_income(
            db,
            tenant_code=tenant_code,
            entry_date=event_date,
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params=params,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# Verified istorijski FBiH / BD applicable period ostaje fail-closed na
# dataset_not_implemented. Temporal resolver ne smije slučajno aktivirati
# neimplementiranu KP-1042 semantiku.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("entity", "scenario_key", "expected_mode"),
    [
        (
            "FBiH",
            "fbih_obrt",
            "fbih_kp1042_pausal_b2b",
        ),
        (
            "BD",
            "bd_samostalna",
            "bd_kp1042_pausal_b2b",
        ),
    ],
)
def test_promet_verified_historical_unsupported_mode_stays_fail_closed(
    entity: str,
    scenario_key: str,
    expected_mode: str,
) -> None:
    tenant_code = _create_tenant("promet-period-unsupported-history")

    with SessionLocal() as db:
        _add_tax_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            entity=entity,
            regime="pausal",
            scenario_key=scenario_key,
        )
        _add_business_period(
            db,
            tenant_code=tenant_code,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            has_noncash_sales_to_legal_entities=True,
        )
        db.commit()

    response = client.get(
        "/promet",
        headers=_headers(tenant_code),
        params={"year": 2026},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "promet_dataset_not_implemented",
        "mode": expected_mode,
    }
