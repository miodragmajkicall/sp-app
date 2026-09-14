from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
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


def _tax_payload(
    *,
    monthly_pension: float | None = 100.0,
    effective_from: str | None = None,
) -> dict:
    payload = {
        "entity": "RS",
        "regime": "two_percent",
        "scenario_key": "rs_primary",
        "has_additional_activity": False,
        "monthly_pension": monthly_pension,
        "monthly_health": 50.0,
        "monthly_unemployment": 10.0,
    }

    if effective_from is not None:
        payload["effective_from"] = effective_from

    return payload


def test_business_profile_legacy_confirmation_and_rollover_preserve_patch_semantics() -> None:
    tenant_code, headers = _create_tenant("business-temporal")

    initial = client.put(
        "/settings/business",
        headers=headers,
        json={
            "sales_locations_count": 2,
            "sells_to_consumers": True,
            "daily_cash_turnover_covered_elsewhere": False,
            "has_noncash_sales_to_legal_entities": True,
        },
    )
    assert initial.status_code == 200, initial.text
    assert initial.json()["effective_from"] is None
    assert initial.json()["effective_to"] is None

    confirm = client.put(
        "/settings/business",
        headers=headers,
        json={"effective_from": "2026-01-01"},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["effective_from"] == "2026-01-01"
    assert confirm.json()["effective_to"] is None

    rollover = client.put(
        "/settings/business",
        headers=headers,
        json={
            "effective_from": "2026-07-01",
            "sales_locations_count": 3,
        },
    )
    assert rollover.status_code == 200, rollover.text

    current = rollover.json()
    assert current["effective_from"] == "2026-07-01"
    assert current["effective_to"] is None
    assert current["sales_locations_count"] == 3

    # PATCH-semantika mora preživjeti rollover:
    # omitted vrijednosti se kopiraju iz prethodnog perioda.
    assert current["sells_to_consumers"] is True
    assert current["daily_cash_turnover_covered_elsewhere"] is False
    assert current["has_noncash_sales_to_legal_entities"] is True

    db = SessionLocal()
    try:
        rows = db.execute(
            select(TenantBusinessProfileSettings)
            .where(
                TenantBusinessProfileSettings.tenant_code
                == tenant_code
            )
            .order_by(TenantBusinessProfileSettings.effective_from)
        ).scalars().all()

        assert len(rows) == 2

        assert rows[0].effective_from == date(2026, 1, 1)
        assert rows[0].effective_to == date(2026, 6, 30)
        assert rows[0].sales_locations_count == 2

        assert rows[1].effective_from == date(2026, 7, 1)
        assert rows[1].effective_to is None
        assert rows[1].sales_locations_count == 3
    finally:
        db.close()

    get_response = client.get(
        "/settings/business",
        headers=headers,
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["effective_from"] == "2026-07-01"
    assert get_response.json()["sales_locations_count"] == 3


def test_tax_profile_legacy_confirmation_and_rollover_preserve_history() -> None:
    tenant_code, headers = _create_tenant("tax-temporal")

    initial = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(),
    )
    assert initial.status_code == 200, initial.text
    assert initial.json()["effective_from"] is None
    assert initial.json()["effective_to"] is None

    confirm = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(effective_from="2026-01-01"),
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["effective_from"] == "2026-01-01"
    assert confirm.json()["effective_to"] is None

    rollover = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(
            monthly_pension=150.0,
            effective_from="2026-07-01",
        ),
    )
    assert rollover.status_code == 200, rollover.text
    assert rollover.json()["effective_from"] == "2026-07-01"
    assert rollover.json()["monthly_pension"] == 150.0

    db = SessionLocal()
    try:
        rows = db.execute(
            select(TenantTaxProfileSettings)
            .where(
                TenantTaxProfileSettings.tenant_code
                == tenant_code
            )
            .order_by(TenantTaxProfileSettings.effective_from)
        ).scalars().all()

        assert len(rows) == 2

        assert rows[0].effective_from == date(2026, 1, 1)
        assert rows[0].effective_to == date(2026, 6, 30)
        assert float(rows[0].monthly_pension) == 100.0

        assert rows[1].effective_from == date(2026, 7, 1)
        assert rows[1].effective_to is None
        assert float(rows[1].monthly_pension) == 150.0
    finally:
        db.close()

    get_response = client.get(
        "/settings/tax",
        headers=headers,
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["effective_from"] == "2026-07-01"
    assert get_response.json()["monthly_pension"] == 150.0


def test_verified_business_profile_requires_effective_from_for_real_change() -> None:
    _, headers = _create_tenant("business-date-required")

    create = client.put(
        "/settings/business",
        headers=headers,
        json={
            "effective_from": "2026-01-01",
            "sales_locations_count": 2,
            "sells_to_consumers": True,
        },
    )
    assert create.status_code == 200, create.text

    change_without_date = client.put(
        "/settings/business",
        headers=headers,
        json={"sales_locations_count": 3},
    )
    assert change_without_date.status_code == 409

    retroactive = client.put(
        "/settings/business",
        headers=headers,
        json={
            "effective_from": "2025-12-31",
            "sales_locations_count": 3,
        },
    )
    assert retroactive.status_code == 409


def test_verified_tax_profile_requires_effective_from_for_real_change() -> None:
    _, headers = _create_tenant("tax-date-required")

    create = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(effective_from="2026-01-01"),
    )
    assert create.status_code == 200, create.text

    # Identičan full-state PUT je dozvoljen kao no-op.
    noop = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(),
    )
    assert noop.status_code == 200, noop.text
    assert noop.json()["effective_from"] == "2026-01-01"

    changed = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(monthly_pension=150.0),
    )
    assert changed.status_code == 409

    retroactive = client.put(
        "/settings/tax",
        headers=headers,
        json=_tax_payload(
            monthly_pension=150.0,
            effective_from="2025-12-31",
        ),
    )
    assert retroactive.status_code == 409
