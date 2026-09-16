from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.models import CashEntry, InputInvoice, TenantTaxProfileSettings
from app.services.recognized_input_expenses import (
    list_recognized_input_expenses, UnsupportedInputExpenseRecognitionError,
)
from app.services.recognized_manual_cash import (
    list_recognized_manual_cash, UnsupportedManualCashRecognitionError,
)

from app.db import SessionLocal
from app.main import app
from app.routes import tax as tax_routes
from app.services import input_invoice_recognition as recognition_service
from app.services.input_invoice_recognition import (
    RecognitionBasis,
    TenantRecognitionContext,
    resolve_stored_input_invoice_recognition,
    resolve_tenant_recognition_context,
)


client = TestClient(app)


def _create_tenant(prefix: str) -> tuple[str, dict[str, str]]:
    tenant_code = f"{prefix}-{uuid4().hex[:8]}"

    response = client.post(
        "/tenants",
        json={
            "code": tenant_code,
            "name": prefix,
        },
    )
    assert response.status_code == 201, response.text

    return tenant_code, {"X-Tenant-Code": tenant_code}


def _put_tax(
    headers: dict[str, str],
    *,
    effective_from: str,
    entity: str = "RS",
    regime: str = "two_percent",
    scenario_key: str = "rs_primary",
    has_additional_activity: bool = False,
) -> None:
    response = client.put(
        "/settings/tax",
        headers=headers,
        json={
            "entity": entity,
            "regime": regime,
            "scenario_key": scenario_key,
            "has_additional_activity": has_additional_activity,
            "effective_from": effective_from,
        },
    )
    assert response.status_code == 200, response.text


def test_promet_capability_uses_current_tax_profile_after_rollover() -> None:
    _, headers = _create_tenant("consumer-promet-current")

    _put_tax(
        headers,
        effective_from="2026-01-01",
        regime="books",
        scenario_key="rs_primary",
    )
    _put_tax(
        headers,
        effective_from="2026-07-01",
        regime="two_percent",
        scenario_key="rs_primary",
    )

    response = client.get(
        "/settings/business/promet-capability",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applicable"
    assert response.json()["mode"] == "rs_small_entrepreneur"


def test_tax_ui_schema_uses_tax_profile_for_explicit_as_of_date() -> None:
    _, headers = _create_tenant("consumer-ui-asof")

    _put_tax(
        headers,
        effective_from="2026-01-01",
        entity="RS",
        regime="two_percent",
        scenario_key="rs_primary",
    )
    _put_tax(
        headers,
        effective_from="2026-07-01",
        entity="FBiH",
        regime="pausal",
        scenario_key="fbih_obrt",
    )

    old_response = client.get(
        "/settings/tax/ui-schema",
        headers=headers,
        params={"as_of": "2026-03-01"},
    )
    assert old_response.status_code == 200, old_response.text
    assert old_response.json()["entity"] == "RS"
    assert old_response.json()["scenario_key"] == "rs_primary"

    new_response = client.get(
        "/settings/tax/ui-schema",
        headers=headers,
        params={"as_of": "2026-08-01"},
    )
    assert new_response.status_code == 200, new_response.text
    assert new_response.json()["entity"] == "FBiH"
    assert new_response.json()["scenario_key"] == "fbih_obrt"


def test_tax_config_resolver_selects_profile_for_requested_as_of(
    monkeypatch,
) -> None:
    tenant_code, headers = _create_tenant("consumer-tax-asof")

    _put_tax(
        headers,
        effective_from="2026-01-01",
        entity="RS",
        regime="pausal",
        scenario_key="rs_primary",
        has_additional_activity=False,
    )
    _put_tax(
        headers,
        effective_from="2026-07-01",
        entity="RS",
        regime="pausal",
        scenario_key="rs_supplementary",
        has_additional_activity=True,
    )

    calls: list[dict[str, object]] = []

    def fake_find_current_constants_set(
        *,
        db,
        jurisdiction,
        as_of,
        scenario_key=None,
    ):
        calls.append(
            {
                "jurisdiction": jurisdiction,
                "as_of": as_of,
                "scenario_key": scenario_key,
            }
        )
        return SimpleNamespace(
            payload={
                "tax": {
                    "income_tax_rate": 0.10,
                    "pension_contribution_rate": 0.18,
                    "health_contribution_rate": 0.12,
                    "unemployment_contribution_rate": 0.015,
                    "flat_costs_rate": 0.30,
                    "currency": "BAM",
                }
            }
        )

    monkeypatch.setattr(
        tax_routes,
        "_find_current_constants_set",
        fake_find_current_constants_set,
    )

    db = SessionLocal()
    try:
        tax_routes._resolve_tax_config(
            db,
            tenant_code,
            as_of=date(2026, 3, 1),
        )
        assert calls[0]["scenario_key"] == "rs_primary"

        calls.clear()

        tax_routes._resolve_tax_config(
            db,
            tenant_code,
            as_of=date(2026, 8, 1),
        )
        assert calls[0]["scenario_key"] == "rs_supplementary"
    finally:
        db.close()


def test_input_invoice_recognition_context_uses_profile_as_of() -> None:
    tenant_code, headers = _create_tenant("consumer-input-asof")

    _put_tax(
        headers,
        effective_from="2026-01-01",
        entity="RS",
        regime="books",
        scenario_key="rs_primary",
    )
    _put_tax(
        headers,
        effective_from="2026-07-01",
        entity="RS",
        regime="two_percent",
        scenario_key="rs_primary",
    )

    db = SessionLocal()
    try:
        old_context = resolve_tenant_recognition_context(
            db,
            tenant_code,
            as_of=date(2026, 3, 1),
        )
        new_context = resolve_tenant_recognition_context(
            db,
            tenant_code,
            as_of=date(2026, 8, 1),
        )
        current_context = resolve_tenant_recognition_context(
            db,
            tenant_code,
        )

        assert old_context.basis is RecognitionBasis.UNRESOLVED
        assert new_context.basis is RecognitionBasis.CASH
        assert current_context.basis is RecognitionBasis.CASH
    finally:
        db.close()


def test_stored_input_invoice_recognition_anchors_context_to_payment_date(
    monkeypatch,
) -> None:
    payment_date = date(2026, 5, 15)
    captured: dict[str, object] = {}

    class ScalarResult:
        def scalar_one_or_none(self):
            return payment_date

    class FakeSession:
        def execute(self, statement):
            return ScalarResult()

    def fake_context(
        db,
        tenant_code,
        *,
        as_of=None,
    ):
        captured["tenant_code"] = tenant_code
        captured["as_of"] = as_of
        return TenantRecognitionContext(
            basis=RecognitionBasis.CASH,
            jurisdiction="RS",
            regime="two_percent",
            scenario_key="rs_primary",
        )

    monkeypatch.setattr(
        recognition_service,
        "resolve_tenant_recognition_context",
        fake_context,
    )

    invoice = SimpleNamespace(
        id=123,
        tenant_code="consumer-input-payment-date",
    )

    result = resolve_stored_input_invoice_recognition(
        FakeSession(),
        invoice,
    )

    assert captured["tenant_code"] == "consumer-input-payment-date"
    assert captured["as_of"] == payment_date
    assert result.recognition_date == payment_date
    assert result.integrity_date == payment_date


@pytest.mark.parametrize("periods", [
    [(None, None)],
    [(date(2026, 7, 1), None)],
    [(date(2026, 1, 1), date(2026, 2, 28))],
    [(date(2026, 1, 1), date(2026, 2, 28)), (date(2026, 7, 1), None)],
])
def test_tax_preview_rejects_unverified_or_missing_profile_coverage(periods):
    tenant, headers = _create_tenant("tax-gap")
    with SessionLocal() as db:
        for start, end in periods:
            db.add(TenantTaxProfileSettings(
                tenant_code=tenant, entity="RS", regime="pausal",
                scenario_key="rs_primary", has_additional_activity=False,
                effective_from=start, effective_to=end,
            ))
        db.commit()
    response = client.get("/tax/monthly/preview", headers=headers, params={
        "year": 2026, "month": 3, "total_income": "1000", "total_expense": "0",
    })
    assert response.status_code == 409, response.text
    assert "profile" in response.json()["detail"].lower()


def test_tax_preview_requires_verified_profile_even_when_tenant_has_no_history():
    _, other_headers = _create_tenant("tax-other-history")
    _put_tax(other_headers, effective_from="2026-01-01")

    _, headers = _create_tenant("tax-no-history")

    response = client.get(
        "/tax/monthly/preview",
        headers=headers,
        params={
            "year": 2026,
            "month": 3,
            "total_income": "1000",
            "total_expense": "0",
        },
    )

    assert response.status_code == 409, response.text
    assert "profile" in response.json()["detail"].lower()


def test_tax_settings_override_cannot_bypass_missing_verified_profile():
    _, headers = _create_tenant("tax-override-no-profile")

    settings_response = client.put(
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
    assert settings_response.status_code == 200, settings_response.text

    response = client.get(
        "/tax/monthly/preview",
        headers=headers,
        params={
            "year": 2026,
            "month": 3,
            "total_income": "1000",
            "total_expense": "0",
        },
    )

    assert response.status_code == 409, response.text
    assert "profile" in response.json()["detail"].lower()


def test_tax_preview_rejects_profile_without_explicit_scenario_key():
    tenant, headers = _create_tenant("tax-missing-scenario")

    with SessionLocal() as db:
        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant,
                entity="RS",
                regime="pausal",
                scenario_key=None,
                has_additional_activity=False,
                effective_from=date(2026, 1, 1),
                effective_to=None,
            )
        )
        db.commit()

    response = client.get(
        "/tax/monthly/preview",
        headers=headers,
        params={
            "year": 2026,
            "month": 3,
            "total_income": "1000",
            "total_expense": "0",
        },
    )

    assert response.status_code == 409, response.text
    assert "scenario_key" in response.json()["detail"]


def test_tax_preview_rejects_unknown_profile_jurisdiction():
    tenant, headers = _create_tenant("tax-unknown-jurisdiction")

    with SessionLocal() as db:
        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant,
                entity="UNKNOWN",
                regime="pausal",
                scenario_key="rs_primary",
                has_additional_activity=False,
                effective_from=date(2026, 1, 1),
                effective_to=None,
            )
        )
        db.commit()

    response = client.get(
        "/tax/monthly/preview",
        headers=headers,
        params={
            "year": 2026,
            "month": 3,
            "total_income": "1000",
            "total_expense": "0",
        },
    )

    assert response.status_code == 409, response.text
    assert "jurisdiction" in response.json()["detail"].lower()


def test_tax_constants_payload_does_not_fill_missing_values_from_dummy_defaults():
    cfg = tax_routes._tax_config_from_constants_payload(
        {
            "tax": {
                "income_tax_rate": 0.10,
            }
        }
    )

    assert cfg is None


def test_tax_resolver_does_not_fallback_to_other_scenario_constants(monkeypatch):
    tenant, headers = _create_tenant("tax-exact-scenario-only")

    _put_tax(
        headers,
        effective_from="2026-01-01",
        entity="RS",
        regime="pausal",
        scenario_key="rs_supplementary",
        has_additional_activity=True,
    )

    calls: list[str | None] = []

    def fake_find_current_constants_set(
        *,
        db,
        jurisdiction,
        as_of,
        scenario_key=None,
    ):
        calls.append(scenario_key)

        if scenario_key is None:
            return SimpleNamespace(
                payload={
                    "tax": {
                        "income_tax_rate": 0.10,
                        "pension_contribution_rate": 0.18,
                        "health_contribution_rate": 0.12,
                        "unemployment_contribution_rate": 0.015,
                        "flat_costs_rate": 0.30,
                        "currency": "BAM",
                    }
                }
            )

        return None

    monkeypatch.setattr(
        tax_routes,
        "_find_current_constants_set",
        fake_find_current_constants_set,
    )

    response = client.get(
        "/tax/monthly/preview",
        headers=headers,
        params={
            "year": 2026,
            "month": 3,
            "total_income": "1000",
            "total_expense": "0",
        },
    )

    assert response.status_code == 409, response.text
    assert calls == ["rs_supplementary"]
    assert "constants" in response.json()["detail"].lower()


def test_tax_verified_profile_without_constants_cannot_use_default(monkeypatch):
    tenant, headers = _create_tenant("tax-no-constants")
    _put_tax(headers, effective_from="2026-01-01")
    monkeypatch.setattr(tax_routes, "_find_current_constants_set", lambda **kwargs: None)
    response = client.get("/tax/monthly/preview", headers=headers, params={
        "year": 2026, "month": 3, "total_income": "1000", "total_expense": "0",
    })
    assert response.status_code == 409, response.text


@pytest.mark.parametrize("source", ["input", "manual"])
@pytest.mark.parametrize("old_regime,new_regime", [
    ("pausal", "books"), ("books", "pausal"), ("pausal", "two_percent"),
])
def test_recognized_events_use_each_event_period(source, old_regime, new_regime):
    tenant, headers = _create_tenant("event-period")
    _put_tax(headers, effective_from="2026-01-01", regime=old_regime)
    _put_tax(headers, effective_from="2026-07-01", regime=new_regime)
    dates = [date(2026, 6, 30), date(2026, 7, 1)]
    with SessionLocal() as db:
        for event_date in dates:
            _add_recognition_event(db, tenant, source, event_date)
        db.commit()
        service, error = _recognition_service(source)
        for index, regime in enumerate((old_regime, new_regime)):
            kwargs = dict(tenant_code=tenant, date_from=dates[index],
                          date_to=date(2026, 7, 1) if index == 0 else date(2026, 7, 2))
            if regime == "books":
                with pytest.raises(error):
                    service(db, **kwargs)
            else:
                result = service(db, **kwargs)
                assert [row.recognition_date for row in result] == [dates[index]]
                assert [row.amount for row in result] == [117]
        if "books" in (old_regime, new_regime):
            with pytest.raises(error):
                service(db, tenant_code=tenant)
        else:
            assert [row.recognition_date for row in service(db, tenant_code=tenant)] == dates


def _recognition_service(source):
    if source == "input":
        return list_recognized_input_expenses, UnsupportedInputExpenseRecognitionError
    return list_recognized_manual_cash, UnsupportedManualCashRecognitionError


def _add_recognition_event(db, tenant, source, event_date):
    invoice_id = None
    if source == "input":
        invoice = InputInvoice(
            tenant_code=tenant, supplier_name="Period supplier",
            invoice_number=uuid4().hex, issue_date=date(2025, 12, 1),
            total_amount=117, is_tax_deductible=True,
        )
        db.add(invoice)
        db.flush()
        invoice_id = invoice.id
    db.add(CashEntry(
        tenant_code=tenant, entry_date=event_date, kind="expense", amount=117,
        account="bank", input_invoice_id=invoice_id,
        recognition_class="business_activity" if source == "manual" else None,
        tax_treatment="deductible" if source == "manual" else None,
    ))


@pytest.mark.parametrize("source", ["input", "manual"])
@pytest.mark.parametrize("start", [None, date(2026, 7, 1)])
def test_recognized_events_fail_closed_without_verified_coverage(source, start):
    tenant, _ = _create_tenant("event-unverified")
    service, error = _recognition_service(source)
    with SessionLocal() as db:
        db.add(TenantTaxProfileSettings(
            tenant_code=tenant, entity="RS", regime="pausal",
            scenario_key="rs_primary", has_additional_activity=False,
            effective_from=start,
        ))
        _add_recognition_event(db, tenant, source, date(2026, 6, 30))
        db.commit()
        with pytest.raises(error):
            service(db, tenant_code=tenant)
        assert service(db, tenant_code=tenant, date_from=date(2026, 7, 1)) == []
