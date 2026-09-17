from __future__ import annotations

from typing import Optional


ALLOWED_TENANT_TAX_SCENARIOS: dict[str, frozenset[str]] = {
    "RS": frozenset({"rs_primary", "rs_supplementary"}),
    "FBiH": frozenset({"fbih_obrt", "fbih_slobodna"}),
    "BD": frozenset({"bd_samostalna"}),
}


class TenantTaxScenarioIntegrityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_tenant_tax_jurisdiction(entity_value: Optional[str]) -> Optional[str]:
    value = (entity_value or "").strip()
    if not value:
        return None

    upper = value.upper()

    if upper == "RS":
        return "RS"

    if upper in {"FBIH", "FEDERACIJA", "FEDERACIJA BIH"}:
        return "FBiH"

    if upper in {
        "BD",
        "BRCKO",
        "BRČKO",
        "BRCKO DISTRIKT",
        "BRČKO DISTRIKT",
    }:
        return "BD"

    return None


def validate_tenant_tax_scenario(
    *,
    jurisdiction: Optional[str],
    scenario_key: Optional[str],
    has_additional_activity: bool,
    require_explicit: bool,
) -> Optional[str]:
    """
    Validate the tenant-side scenario identity.

    This validates tenant facts only. It does not decide legal rates,
    contribution bases or other statutory policy values.

    FBiH scenario choice remains explicit until TAX-5 introduces enough
    verified tenant facts to derive it safely.
    """
    if jurisdiction not in ALLOWED_TENANT_TAX_SCENARIOS:
        raise TenantTaxScenarioIntegrityError(
            "tax_profile_jurisdiction_unsupported",
            f"Tax profile jurisdiction is missing or unsupported: {jurisdiction!r}",
        )

    scenario = (scenario_key or "").strip()

    if not scenario:
        if require_explicit:
            raise TenantTaxScenarioIntegrityError(
                "tax_profile_scenario_missing",
                "Tax profile scenario_key is required for a verified profile",
            )
        return None

    allowed = ALLOWED_TENANT_TAX_SCENARIOS[jurisdiction]
    if scenario not in allowed:
        raise TenantTaxScenarioIntegrityError(
            "tax_profile_scenario_jurisdiction_mismatch",
            (
                f"Tax profile scenario_key '{scenario}' is not valid for "
                f"jurisdiction '{jurisdiction}'"
            ),
        )

    if jurisdiction == "RS":
        expected = (
            "rs_supplementary"
            if has_additional_activity
            else "rs_primary"
        )

        if scenario != expected:
            raise TenantTaxScenarioIntegrityError(
                "tax_profile_scenario_fact_mismatch",
                (
                    f"Tax profile scenario_key '{scenario}' conflicts with "
                    f"has_additional_activity={has_additional_activity}; "
                    f"expected '{expected}'"
                ),
            )

    return scenario
