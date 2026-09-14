from __future__ import annotations

from sqlalchemy import inspect

from app.db import engine
from app.models import (
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
)


PROFILE_TABLES = (
    (
        "tenant_tax_profile_settings",
        TenantTaxProfileSettings,
        "ck_tenant_tax_profile_effective_range",
        "uq_tenant_tax_profile_open_period",
        "ix_tenant_tax_profile_effective_period",
    ),
    (
        "tenant_business_profile_settings",
        TenantBusinessProfileSettings,
        "ck_tenant_business_profile_effective_range",
        "uq_tenant_business_profile_open_period",
        "ix_tenant_business_profile_effective_period",
    ),
)


def test_profile_models_expose_effective_period_contract() -> None:
    for _, model, _, _, _ in PROFILE_TABLES:
        assert "effective_from" in model.__table__.c
        assert "effective_to" in model.__table__.c

        assert model.__table__.c.effective_from.nullable is True
        assert model.__table__.c.effective_to.nullable is True

        # Istorija zahtijeva više redova istog tenanta.
        assert model.__table__.c.tenant_code.unique is not True


def test_profile_database_schema_supports_effective_dated_history() -> None:
    inspector = inspect(engine)

    for (
        table_name,
        _,
        range_check_name,
        open_period_index_name,
        period_index_name,
    ) in PROFILE_TABLES:
        columns = {
            column["name"]: column
            for column in inspector.get_columns(table_name)
        }

        assert "effective_from" in columns
        assert "effective_to" in columns
        assert columns["effective_from"]["nullable"] is True
        assert columns["effective_to"]["nullable"] is True

        unique_constraints = inspector.get_unique_constraints(table_name)

        assert not any(
            constraint.get("column_names") == ["tenant_code"]
            for constraint in unique_constraints
        )

        check_names = {
            constraint.get("name")
            for constraint in inspector.get_check_constraints(table_name)
        }
        assert range_check_name in check_names

        indexes = {
            index["name"]: index
            for index in inspector.get_indexes(table_name)
        }

        assert open_period_index_name in indexes
        assert indexes[open_period_index_name]["unique"] is True
        assert indexes[open_period_index_name]["column_names"] == ["tenant_code"]

        assert period_index_name in indexes
        assert indexes[period_index_name]["unique"] is False
        assert indexes[period_index_name]["column_names"] == [
            "tenant_code",
            "effective_from",
            "effective_to",
        ]


def test_profile_database_constraints_enforce_effective_period_integrity() -> None:
    from datetime import date
    from uuid import uuid4

    import pytest
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.main import app

    client = TestClient(app)

    def create_tenant(prefix: str) -> str:
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

    # --------------------------------------------------------
    # Tax profile — range contract
    # --------------------------------------------------------
    tenant_code = create_tenant("tax-period-range")

    db = SessionLocal()
    try:
        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant_code,
                entity="RS",
                regime="two_percent",
                scenario_key="rs_primary",
                has_additional_activity=False,
                effective_from=None,
                effective_to=date(2026, 12, 31),
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()

        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant_code,
                entity="RS",
                regime="two_percent",
                scenario_key="rs_primary",
                has_additional_activity=False,
                effective_from=date(2026, 12, 31),
                effective_to=date(2026, 1, 1),
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()
    finally:
        db.close()

    # --------------------------------------------------------
    # Tax profile — at most one open-ended row
    # --------------------------------------------------------
    tenant_code = create_tenant("tax-open-period")

    db = SessionLocal()
    try:
        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant_code,
                entity="RS",
                regime="two_percent",
                scenario_key="rs_primary",
                has_additional_activity=False,
                effective_from=None,
                effective_to=None,
            )
        )
        db.flush()

        db.add(
            TenantTaxProfileSettings(
                tenant_code=tenant_code,
                entity="RS",
                regime="two_percent",
                scenario_key="rs_primary",
                has_additional_activity=False,
                effective_from=date(2026, 9, 14),
                effective_to=None,
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()
    finally:
        db.close()

    # --------------------------------------------------------
    # Business profile — range contract
    # --------------------------------------------------------
    tenant_code = create_tenant("business-period-range")

    db = SessionLocal()
    try:
        db.add(
            TenantBusinessProfileSettings(
                tenant_code=tenant_code,
                sales_locations_count=1,
                effective_from=None,
                effective_to=date(2026, 12, 31),
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()

        db.add(
            TenantBusinessProfileSettings(
                tenant_code=tenant_code,
                sales_locations_count=1,
                effective_from=date(2026, 12, 31),
                effective_to=date(2026, 1, 1),
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()
    finally:
        db.close()

    # --------------------------------------------------------
    # Business profile — at most one open-ended row.
    # Prvi NULL/NULL red ujedno dokazuje da legacy period ostaje dozvoljen.
    # --------------------------------------------------------
    tenant_code = create_tenant("business-open-period")

    db = SessionLocal()
    try:
        db.add(
            TenantBusinessProfileSettings(
                tenant_code=tenant_code,
                sales_locations_count=1,
                effective_from=None,
                effective_to=None,
            )
        )
        db.flush()

        db.add(
            TenantBusinessProfileSettings(
                tenant_code=tenant_code,
                sales_locations_count=2,
                effective_from=date(2026, 9, 14),
                effective_to=None,
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()
    finally:
        db.close()


def test_profile_model_metadata_declares_effective_period_indexes() -> None:
    for (
        _,
        model,
        _,
        open_period_index_name,
        period_index_name,
    ) in PROFILE_TABLES:
        indexes = {
            index.name: index
            for index in model.__table__.indexes
        }

        assert open_period_index_name in indexes

        open_period_index = indexes[open_period_index_name]
        assert open_period_index.unique is True
        assert [
            column.name
            for column in open_period_index.columns
        ] == ["tenant_code"]
        assert (
            open_period_index.dialect_options["postgresql"]["where"]
            is not None
        )

        assert period_index_name in indexes

        period_index = indexes[period_index_name]
        assert period_index.unique is False
        assert [
            column.name
            for column in period_index.columns
        ] == [
            "tenant_code",
            "effective_from",
            "effective_to",
        ]
