from __future__ import annotations

import pytest

from app.services.promet_eligibility import (
    PrometEligibilityStatus,
    PrometMode,
    resolve_promet_eligibility,
)


def test_missing_entity_needs_configuration() -> None:
    result = resolve_promet_eligibility(
        entity=None,
        regime=None,
        scenario_key=None,
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.mode is None
    assert result.blocking_fields == ("entity",)


def test_missing_scenario_needs_configuration() -> None:
    result = resolve_promet_eligibility(
        entity="RS",
        regime="two_percent",
        scenario_key=None,
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == ("scenario_key",)


def test_scenario_must_match_entity() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="books",
        scenario_key="rs_primary",
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.reason_code == "scenario_not_valid_for_entity"


@pytest.mark.parametrize(
    "regime",
    ["two_percent", "small_entrepreneur_2pct"],
)
def test_rs_small_entrepreneur_requires_promet(
    regime: str,
) -> None:
    result = resolve_promet_eligibility(
        entity="RS",
        regime=regime,
        scenario_key="rs_primary",
    )

    assert result.status is PrometEligibilityStatus.APPLICABLE
    assert result.mode is PrometMode.RS_SMALL_ENTREPRENEUR


def test_rs_books_does_not_use_promet_module() -> None:
    result = resolve_promet_eligibility(
        entity="RS",
        regime="books",
        scenario_key="rs_primary",
    )

    assert result.status is PrometEligibilityStatus.NOT_APPLICABLE
    assert result.mode is None


def test_rs_legacy_pausal_is_not_silently_interpreted() -> None:
    result = resolve_promet_eligibility(
        entity="RS",
        regime="pausal",
        scenario_key="rs_primary",
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == ("regime",)


def test_fbih_pausal_b2b_requires_kp1042() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
        has_noncash_sales_to_legal_entities=True,
    )

    assert result.status is PrometEligibilityStatus.APPLICABLE
    assert result.mode is PrometMode.FBIH_KP1042_PAUSAL_B2B


def test_fbih_pausal_without_b2b_is_not_applicable() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
        has_noncash_sales_to_legal_entities=False,
    )

    assert result.status is PrometEligibilityStatus.NOT_APPLICABLE
    assert result.mode is None


def test_fbih_pausal_missing_b2b_fact_needs_configuration() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == (
        "has_noncash_sales_to_legal_entities",
    )


def test_fbih_slobodna_pausal_is_not_assumed_valid() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_slobodna",
        has_noncash_sales_to_legal_entities=True,
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.reason_code == (
        "fbih_pausal_not_supported_for_scenario"
    )


def test_fbih_books_multi_location_requires_kp1042() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="books",
        scenario_key="fbih_obrt",
        sales_locations_count=2,
        sells_to_consumers=True,
        daily_cash_turnover_covered_elsewhere=False,
    )

    assert result.status is PrometEligibilityStatus.APPLICABLE
    assert result.mode is PrometMode.FBIH_KP1042_MULTI_LOCATION


@pytest.mark.parametrize(
    (
        "sales_locations_count",
        "sells_to_consumers",
        "covered_elsewhere",
    ),
    [
        (1, True, False),
        (2, False, False),
        (2, True, True),
    ],
)
def test_fbih_books_known_negative_fact_is_not_applicable(
    sales_locations_count: int,
    sells_to_consumers: bool,
    covered_elsewhere: bool,
) -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="books",
        scenario_key="fbih_obrt",
        sales_locations_count=sales_locations_count,
        sells_to_consumers=sells_to_consumers,
        daily_cash_turnover_covered_elsewhere=covered_elsewhere,
    )

    assert result.status is PrometEligibilityStatus.NOT_APPLICABLE


def test_fbih_books_partial_profile_needs_only_unknown_facts() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="books",
        scenario_key="fbih_obrt",
        sales_locations_count=2,
        sells_to_consumers=True,
        daily_cash_turnover_covered_elsewhere=None,
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == (
        "daily_cash_turnover_covered_elsewhere",
    )


def test_fbih_legacy_two_percent_is_not_silently_books() -> None:
    result = resolve_promet_eligibility(
        entity="FBiH",
        regime="two_percent",
        scenario_key="fbih_obrt",
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == ("regime",)


def test_bd_pausal_b2b_requires_kp1042() -> None:
    result = resolve_promet_eligibility(
        entity="Brcko",
        regime="pausal",
        scenario_key="bd_samostalna",
        has_noncash_sales_to_legal_entities=True,
    )

    assert result.status is PrometEligibilityStatus.APPLICABLE
    assert result.mode is PrometMode.BD_KP1042_PAUSAL_B2B


def test_bd_pausal_without_b2b_is_not_applicable() -> None:
    result = resolve_promet_eligibility(
        entity="BD",
        regime="pausal",
        scenario_key="bd_samostalna",
        has_noncash_sales_to_legal_entities=False,
    )

    assert result.status is PrometEligibilityStatus.NOT_APPLICABLE


def test_bd_pausal_missing_b2b_fact_needs_configuration() -> None:
    result = resolve_promet_eligibility(
        entity="Brčko",
        regime="pausal",
        scenario_key="bd_samostalna",
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == (
        "has_noncash_sales_to_legal_entities",
    )


def test_bd_books_multi_location_requires_kp1042() -> None:
    result = resolve_promet_eligibility(
        entity="Brcko",
        regime="books",
        scenario_key="bd_samostalna",
        sales_locations_count=3,
        sells_to_consumers=True,
        daily_cash_turnover_covered_elsewhere=False,
    )

    assert result.status is PrometEligibilityStatus.APPLICABLE
    assert result.mode is PrometMode.BD_KP1042_MULTI_LOCATION


def test_bd_books_single_location_is_not_applicable() -> None:
    result = resolve_promet_eligibility(
        entity="BD",
        regime="books",
        scenario_key="bd_samostalna",
        sales_locations_count=1,
    )

    assert result.status is PrometEligibilityStatus.NOT_APPLICABLE


def test_bd_legacy_two_percent_needs_configuration() -> None:
    result = resolve_promet_eligibility(
        entity="BD",
        regime="two_percent",
        scenario_key="bd_samostalna",
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.blocking_fields == ("regime",)

def test_rs_scenario_fact_mismatch_needs_configuration_when_fact_is_known() -> None:
    result = resolve_promet_eligibility(
        entity="RS",
        regime="two_percent",
        scenario_key="rs_primary",
        has_additional_activity=True,
    )

    assert result.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
    assert result.mode is None
    assert result.reason_code == "tax_profile_scenario_fact_mismatch"
    assert result.blocking_fields == (
        "scenario_key",
        "has_additional_activity",
    )
