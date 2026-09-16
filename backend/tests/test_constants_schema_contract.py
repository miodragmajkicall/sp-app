from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.constants import (
    CANONICAL_LEGAL_CONSTANTS_SCHEMA_VERSION,
    LegalConstantsPayloadV1,
    validate_legal_constants_payload,
)


def _canonical_payload() -> dict:
    return {
        "schema_version": CANONICAL_LEGAL_CONSTANTS_SCHEMA_VERSION,
        "scenario_key": "rs_primary",
        "base": {
            "currency": "BAM",
            "avg_gross_wage_prev_year_bam": 2000,
            "contrib_base_percent_of_avg_gross": 80,
            "calculated_contrib_base_bam": 1600,
        },
        "tax": {
            "income_tax_rate": 0.10,
            "flat_costs_rate": 0,
            "flat_tax_monthly_amount_bam": 0,
        },
        "contributions": {
            "pension_rate": 0.18,
            "health_rate": 0.12,
            "unemployment_rate": 0.015,
            "pension_amount_bam": 288,
            "health_amount_bam": 192,
            "unemployment_amount_bam": 24,
            "total_contrib_amount_bam": 504,
        },
        "vat": {
            "standard_rate": 0.17,
            "entry_threshold_bam": 0,
        },
        "meta": {
            "source_note": "test",
            "source_reference": "test-reference",
        },
    }


def test_canonical_payload_is_parsed_as_typed_decimal_contract():
    parsed = validate_legal_constants_payload(
        jurisdiction="RS",
        scenario_key="rs_primary",
        payload=_canonical_payload(),
    )

    assert isinstance(parsed, LegalConstantsPayloadV1)
    assert parsed.base.currency == "BAM"
    assert parsed.tax.income_tax_rate == Decimal("0.1")
    assert parsed.contributions.pension_rate == Decimal("0.18")


def test_zero_is_preserved_and_is_not_treated_as_missing():
    parsed = validate_legal_constants_payload(
        jurisdiction="RS",
        scenario_key="rs_primary",
        payload=_canonical_payload(),
    )

    assert parsed is not None
    assert parsed.tax.flat_costs_rate == Decimal("0")
    assert parsed.tax.flat_tax_monthly_amount_bam == Decimal("0")
    assert parsed.vat is not None
    assert parsed.vat.entry_threshold_bam == Decimal("0")


def test_missing_optional_value_remains_none_not_zero():
    payload = _canonical_payload()
    payload["tax"].pop("flat_costs_rate")

    parsed = validate_legal_constants_payload(
        jurisdiction="RS",
        scenario_key="rs_primary",
        payload=payload,
    )

    assert parsed is not None
    assert parsed.tax.flat_costs_rate is None


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("tax", "income_tax_rate", -0.01),
        ("tax", "income_tax_rate", 1.01),
        ("tax", "flat_costs_rate", -0.01),
        ("tax", "flat_costs_rate", 1.01),
        ("contributions", "pension_rate", -0.01),
        ("contributions", "pension_rate", 1.01),
        ("vat", "standard_rate", -0.01),
        ("vat", "standard_rate", 1.01),
        ("base", "contrib_base_percent_of_avg_gross", -1),
        ("base", "contrib_base_percent_of_avg_gross", 101),
    ],
)
def test_out_of_range_values_are_rejected(section, field, value):
    payload = _canonical_payload()
    payload[section][field] = value

    with pytest.raises(ValueError):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_decimals_are_rejected(value):
    payload = _canonical_payload()
    payload["tax"]["income_tax_rate"] = value

    with pytest.raises(ValueError):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


@pytest.mark.parametrize("value", [True, False])
def test_boolean_is_not_accepted_as_numeric_legal_constant(value):
    payload = _canonical_payload()
    payload["tax"]["income_tax_rate"] = value

    with pytest.raises(ValueError):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


def test_blank_currency_is_rejected():
    payload = _canonical_payload()
    payload["base"]["currency"] = "   "

    with pytest.raises(ValueError):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


def test_unknown_canonical_field_is_rejected():
    payload = _canonical_payload()
    payload["tax"]["invented_rate"] = 0.25

    with pytest.raises(ValueError):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


def test_payload_scenario_must_match_outer_scenario():
    payload = _canonical_payload()
    payload["scenario_key"] = "rs_supplementary"

    with pytest.raises(ValueError, match="must match outer scenario_key"):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


def test_outer_scenario_must_belong_to_jurisdiction():
    payload = _canonical_payload()
    payload["scenario_key"] = "fbih_obrt"

    with pytest.raises(ValueError):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="fbih_obrt",
            payload=payload,
        )


def test_legacy_payload_without_schema_version_is_explicitly_unverified():
    legacy = {
        "scenario_key": "rs_primary",
        "tax": {
            "income_tax_rate": 0.10,
        },
    }

    parsed = validate_legal_constants_payload(
        jurisdiction="RS",
        scenario_key="rs_primary",
        payload=legacy,
    )

    assert parsed is None


def test_unknown_declared_schema_version_is_rejected():
    payload = _canonical_payload()
    payload["schema_version"] = "legal-constants-v999"

    with pytest.raises(ValueError, match="Unsupported legal constants schema_version"):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )


@pytest.mark.parametrize("payload", [None, [], "{}", 123])
def test_payload_must_be_json_object(payload):
    with pytest.raises(ValueError, match="payload must be a JSON object"):
        validate_legal_constants_payload(
            jurisdiction="RS",
            scenario_key="rs_primary",
            payload=payload,
        )
