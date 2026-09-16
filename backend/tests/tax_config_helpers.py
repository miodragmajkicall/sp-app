from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models import AppConstantsSet


def set_recognition_test_tax_rates(client: TestClient, headers: dict[str, str]) -> None:
    """Configure explicit legacy rates used by calculation regression tests."""
    response = client.put(
        "/tax/settings",
        headers=headers,
        json={
            "income_tax_rate": "0.10",
            "pension_contribution_rate": "0.18",
            "health_contribution_rate": "0.12",
            "unemployment_contribution_rate": "0.015",
            "flat_costs_rate": "0.30",
            "currency": "BAM",
        },
    )
    assert response.status_code == 200, response.text


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _strict_test_constants_payload_is_complete(payload: dict) -> bool:
    """Check only whether the current legacy TAX calculator can consume the set."""
    tax_block = payload.get("tax") if isinstance(payload.get("tax"), dict) else {}
    contrib_block = (
        payload.get("contributions")
        if isinstance(payload.get("contributions"), dict)
        else {}
    )
    base_block = payload.get("base") if isinstance(payload.get("base"), dict) else {}

    income_tax_rate = _first_present(
        tax_block.get("income_tax_rate"),
        payload.get("income_tax_rate"),
    )
    pension_rate = _first_present(
        tax_block.get("pension_contribution_rate"),
        contrib_block.get("pension_rate"),
        contrib_block.get("pension_contribution_rate"),
        payload.get("pension_contribution_rate"),
    )
    health_rate = _first_present(
        tax_block.get("health_contribution_rate"),
        contrib_block.get("health_rate"),
        contrib_block.get("health_contribution_rate"),
        payload.get("health_contribution_rate"),
    )
    unemployment_rate = _first_present(
        tax_block.get("unemployment_contribution_rate"),
        contrib_block.get("unemployment_rate"),
        contrib_block.get("unemployment_contribution_rate"),
        payload.get("unemployment_contribution_rate"),
    )
    flat_costs_rate = _first_present(
        tax_block.get("flat_costs_rate"),
        payload.get("flat_costs_rate"),
    )
    currency = _first_present(
        base_block.get("currency"),
        tax_block.get("currency"),
        payload.get("currency"),
    )

    return (
        income_tax_rate is not None
        and pension_rate is not None
        and health_rate is not None
        and unemployment_rate is not None
        and flat_costs_rate is not None
        and currency is not None
        and bool(str(currency).strip())
    )


def set_strict_tax_test_context(
    client: TestClient,
    headers: dict[str, str],
    *,
    effective_from: str = "2025-01-01",
    regime: str = "pausal",
    scenario_key: str = "rs_primary",
    has_additional_activity: bool = False,
) -> None:
    """Create a deterministic strict TAX prerequisite without destructive cleanup.

    Existing global legal constants are never deleted or rewritten here.

    If one complete open-ended RS/scenario set already covers effective_from,
    it is reused. If no set covers the date, a complete test set is created.
    Ambiguous, bounded or incomplete existing coverage fails loudly instead of
    silently changing global constants owned by another test.
    """
    as_of = date.fromisoformat(effective_from)

    with SessionLocal() as db:
        rows = db.execute(
            select(AppConstantsSet)
            .where(
                AppConstantsSet.jurisdiction == "RS",
                AppConstantsSet.scenario_key == scenario_key,
                AppConstantsSet.effective_from <= as_of,
                or_(
                    AppConstantsSet.effective_to.is_(None),
                    AppConstantsSet.effective_to >= as_of,
                ),
            )
            .order_by(
                AppConstantsSet.effective_from.desc(),
                AppConstantsSet.id.desc(),
            )
            .limit(2)
        ).scalars().all()

        if len(rows) > 1:
            raise AssertionError(
                "Strict TAX test fixture found overlapping global constants "
                f"for RS/{scenario_key} at {effective_from}; refusing to hide "
                "constants integrity corruption."
            )

        existing = rows[0] if rows else None

        if existing is not None:
            if existing.effective_to is not None:
                raise AssertionError(
                    "Strict TAX test fixture found bounded existing constants "
                    f"for RS/{scenario_key} at {effective_from}; refusing to "
                    "rewrite or delete unrelated global legal constants."
                )

            if not _strict_test_constants_payload_is_complete(
                existing.payload or {}
            ):
                raise AssertionError(
                    "Strict TAX test fixture found incomplete existing constants "
                    f"for RS/{scenario_key} at {effective_from}; refusing to "
                    "complete another test's/global constants implicitly."
                )

    if existing is None:
        constants_response = client.post(
            "/admin/constants",
            json={
                "jurisdiction": "RS",
                "scenario_key": scenario_key,
                "effective_from": effective_from,
                "effective_to": None,
                "payload": {
                    "tax": {
                        "income_tax_rate": 0.10,
                        "pension_contribution_rate": 0.18,
                        "health_contribution_rate": 0.12,
                        "unemployment_contribution_rate": 0.015,
                        "flat_costs_rate": 0.30,
                        "currency": "BAM",
                    }
                },
                "created_by": "tax-test",
                "created_reason": "Deterministic strict TAX test context",
            },
        )
        assert constants_response.status_code == 200, constants_response.text

    profile_response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": "RS",
            "effective_from": effective_from,
            "regime": regime,
            "scenario_key": scenario_key,
            "has_additional_activity": has_additional_activity,
            "monthly_pension": None,
            "monthly_health": None,
            "monthly_unemployment": None,
        },
    )
    assert profile_response.status_code == 200, profile_response.text

    set_recognition_test_tax_rates(client, headers)
