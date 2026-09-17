from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.services.profile_history import (
    get_current_business_profile,
    get_current_tax_profile,
)
from app.services.tax_profile_scenario import (
    ALLOWED_TENANT_TAX_SCENARIOS,
    TenantTaxScenarioIntegrityError,
    normalize_tenant_tax_jurisdiction,
    validate_tenant_tax_scenario,
)


class PrometEligibilityStatus(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_CONFIGURATION = "needs_configuration"


class PrometMode(str, Enum):
    RS_SMALL_ENTREPRENEUR = "rs_small_entrepreneur"
    FBIH_KP1042_MULTI_LOCATION = "fbih_kp1042_multi_location"
    FBIH_KP1042_PAUSAL_B2B = "fbih_kp1042_pausal_b2b"
    BD_KP1042_MULTI_LOCATION = "bd_kp1042_multi_location"
    BD_KP1042_PAUSAL_B2B = "bd_kp1042_pausal_b2b"


@dataclass(frozen=True)
class PrometEligibility:
    status: PrometEligibilityStatus
    mode: PrometMode | None
    reason_code: str
    blocking_fields: tuple[str, ...] = ()


def _normalize_entity(value: str | None) -> str | None:
    jurisdiction = normalize_tenant_tax_jurisdiction(value)

    # Promet interni kod istorijski koristi "FBIH", dok centralni tenant
    # scenario contract koristi canonical "FBiH".
    if jurisdiction == "FBiH":
        return "FBIH"

    return jurisdiction


def _normalize_regime(
    entity: str,
    value: str | None,
) -> str | None:
    raw = (value or "").strip().lower()

    if entity == "RS":
        if raw in {"two_percent", "small_entrepreneur_2pct"}:
            return "small_entrepreneur_2pct"

        if raw == "books":
            return "books"

        # Legacy "pausal" za RS ne mapiramo tiho:
        # postojeći V1 naziv nije dovoljno precizan da dokaže
        # status malog preduzetnika ili redovno vođenje knjiga.
        return None

    if entity in {"FBIH", "BD"}:
        if raw == "pausal":
            return "pausal"

        if raw == "books":
            return "books"

        # Legacy "two_percent" nema sigurno značenje izvan RS.
        return None

    return None


def _needs(
    reason_code: str,
    *blocking_fields: str,
) -> PrometEligibility:
    return PrometEligibility(
        status=PrometEligibilityStatus.NEEDS_CONFIGURATION,
        mode=None,
        reason_code=reason_code,
        blocking_fields=tuple(blocking_fields),
    )


def _not_applicable(reason_code: str) -> PrometEligibility:
    return PrometEligibility(
        status=PrometEligibilityStatus.NOT_APPLICABLE,
        mode=None,
        reason_code=reason_code,
    )


def _applicable(
    mode: PrometMode,
    reason_code: str,
) -> PrometEligibility:
    return PrometEligibility(
        status=PrometEligibilityStatus.APPLICABLE,
        mode=mode,
        reason_code=reason_code,
    )


def _scenario_integrity_needs(
    exc: TenantTaxScenarioIntegrityError,
) -> PrometEligibility:
    if exc.code == "tax_profile_jurisdiction_unsupported":
        return _needs(exc.code, "entity")

    if exc.code == "tax_profile_scenario_fact_mismatch":
        return _needs(
            exc.code,
            "scenario_key",
            "has_additional_activity",
        )

    return _needs(exc.code, "scenario_key")


def _resolve_multi_location_books(
    *,
    entity: str,
    sales_locations_count: int | None,
    sells_to_consumers: bool | None,
    daily_cash_turnover_covered_elsewhere: bool | None,
) -> PrometEligibility:
    # Poznata negativna činjenica je dovoljna da isključi ovaj KP slučaj.
    if sales_locations_count is not None and sales_locations_count <= 1:
        return _not_applicable(
            f"{entity.lower()}_books_single_or_no_sales_location"
        )

    if sells_to_consumers is False:
        return _not_applicable(
            f"{entity.lower()}_books_no_consumer_sales"
        )

    if daily_cash_turnover_covered_elsewhere is True:
        return _not_applicable(
            f"{entity.lower()}_books_daily_turnover_covered_elsewhere"
        )

    missing: list[str] = []

    if sales_locations_count is None:
        missing.append("sales_locations_count")

    if sells_to_consumers is None:
        missing.append("sells_to_consumers")

    if daily_cash_turnover_covered_elsewhere is None:
        missing.append("daily_cash_turnover_covered_elsewhere")

    if missing:
        return _needs(
            f"{entity.lower()}_books_business_profile_incomplete",
            *missing,
        )

    if entity == "FBIH":
        return _applicable(
            PrometMode.FBIH_KP1042_MULTI_LOCATION,
            "fbih_books_multi_location_kp1042",
        )

    return _applicable(
        PrometMode.BD_KP1042_MULTI_LOCATION,
        "bd_books_multi_location_kp1042",
    )


def resolve_promet_eligibility(
    *,
    entity: str | None,
    regime: str | None,
    scenario_key: str | None,
    has_additional_activity: bool | None = None,
    sales_locations_count: int | None = None,
    sells_to_consumers: bool | None = None,
    daily_cash_turnover_covered_elsewhere: bool | None = None,
    has_noncash_sales_to_legal_entities: bool | None = None,
) -> PrometEligibility:
    jurisdiction = normalize_tenant_tax_jurisdiction(entity)
    normalized_entity = _normalize_entity(entity)

    if jurisdiction is None or normalized_entity is None:
        return _needs("unsupported_or_missing_entity", "entity")

    scenario = (scenario_key or "").strip()

    # Kada consumer ima stvarni tenant fact, koristi se isti canonical
    # scenario-integrity contract kao Settings, TAX i recognition.
    if has_additional_activity is not None:
        try:
            canonical_scenario = validate_tenant_tax_scenario(
                jurisdiction=jurisdiction,
                scenario_key=scenario or None,
                has_additional_activity=has_additional_activity,
                require_explicit=True,
            )
        except TenantTaxScenarioIntegrityError as exc:
            return _scenario_integrity_needs(exc)

        assert canonical_scenario is not None
        scenario = canonical_scenario
    else:
        # Čisti rule-level resolver zadržava postojeći API za testiranje
        # Promet pravila kada tenant fact nije dio ulaza.
        if not scenario:
            return _needs("scenario_missing", "scenario_key")

        if scenario not in ALLOWED_TENANT_TAX_SCENARIOS[jurisdiction]:
            return _needs(
                "scenario_not_valid_for_entity",
                "scenario_key",
            )

    normalized_regime = _normalize_regime(
        normalized_entity,
        regime,
    )

    if normalized_regime is None:
        return _needs(
            "regime_ambiguous_or_unsupported",
            "regime",
        )

    # Republika Srpska:
    # mali preduzetnik vodi Knjigu prometa;
    # redovni books scenario koristi druge propisane knjige/evidencije.
    if normalized_entity == "RS":
        if normalized_regime == "small_entrepreneur_2pct":
            return _applicable(
                PrometMode.RS_SMALL_ENTREPRENEUR,
                "rs_small_entrepreneur_promet",
            )

        return _not_applicable(
            "rs_books_promet_not_applicable"
        )

    # FBiH: paušalni KP-1042 slučaj vežemo samo za obrt scenario.
    if normalized_entity == "FBIH" and normalized_regime == "pausal":
        if scenario != "fbih_obrt":
            return _needs(
                "fbih_pausal_not_supported_for_scenario",
                "regime",
            )

        if has_noncash_sales_to_legal_entities is None:
            return _needs(
                "fbih_pausal_b2b_status_missing",
                "has_noncash_sales_to_legal_entities",
            )

        if has_noncash_sales_to_legal_entities:
            return _applicable(
                PrometMode.FBIH_KP1042_PAUSAL_B2B,
                "fbih_pausal_noncash_b2b_kp1042",
            )

        return _not_applicable(
            "fbih_pausal_without_noncash_b2b"
        )

    # Brčko: poseban paušalni bezgotovinski B2B slučaj.
    if normalized_entity == "BD" and normalized_regime == "pausal":
        if has_noncash_sales_to_legal_entities is None:
            return _needs(
                "bd_pausal_b2b_status_missing",
                "has_noncash_sales_to_legal_entities",
            )

        if has_noncash_sales_to_legal_entities:
            return _applicable(
                PrometMode.BD_KP1042_PAUSAL_B2B,
                "bd_pausal_noncash_b2b_kp1042",
            )

        return _not_applicable(
            "bd_pausal_without_noncash_b2b"
        )

    return _resolve_multi_location_books(
        entity=normalized_entity,
        sales_locations_count=sales_locations_count,
        sells_to_consumers=sells_to_consumers,
        daily_cash_turnover_covered_elsewhere=(
            daily_cash_turnover_covered_elsewhere
        ),
    )

def resolve_tenant_promet_eligibility(
    *,
    db: Session,
    tenant_code: str,
) -> PrometEligibility:
    """
    Read-only adapter između tenant settings podataka i čistog
    Promet eligibility resolvera.

    Važno:
    - ne kreira tenant niti settings redove;
    - ne koristi synthetic/default vrijednosti iz Settings API-ja;
    - odsustvo tax/business profila ostavlja kao nepoznate činjenice.
    """
    tax_profile = get_current_tax_profile(
        db,
        tenant_code,
    )

    business_profile = get_current_business_profile(
        db,
        tenant_code,
    )

    return resolve_promet_eligibility(
        entity=tax_profile.entity if tax_profile is not None else None,
        regime=tax_profile.regime if tax_profile is not None else None,
        scenario_key=(
            tax_profile.scenario_key
            if tax_profile is not None
            else None
        ),
        has_additional_activity=(
            tax_profile.has_additional_activity
            if tax_profile is not None
            else None
        ),
        sales_locations_count=(
            business_profile.sales_locations_count
            if business_profile is not None
            else None
        ),
        sells_to_consumers=(
            business_profile.sells_to_consumers
            if business_profile is not None
            else None
        ),
        daily_cash_turnover_covered_elsewhere=(
            business_profile.daily_cash_turnover_covered_elsewhere
            if business_profile is not None
            else None
        ),
        has_noncash_sales_to_legal_entities=(
            business_profile.has_noncash_sales_to_legal_entities
            if business_profile is not None
            else None
        ),
    )
