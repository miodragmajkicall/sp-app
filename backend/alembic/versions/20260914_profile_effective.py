"""Add effective periods to tenant profile settings.

Revision ID: 20260914_profile_effective
Revises: 20260910_business_profile
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260914_profile_effective"
down_revision: Union[str, None] = "20260910_business_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows intentionally remain NULL/NULL:
    # created_at is not evidence of when the legal/business profile
    # became effective.
    op.add_column(
        "tenant_tax_profile_settings",
        sa.Column("effective_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "tenant_tax_profile_settings",
        sa.Column("effective_to", sa.Date(), nullable=True),
    )

    op.add_column(
        "tenant_business_profile_settings",
        sa.Column("effective_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "tenant_business_profile_settings",
        sa.Column("effective_to", sa.Date(), nullable=True),
    )

    op.drop_constraint(
        "tenant_tax_profile_settings_tenant_code_key",
        "tenant_tax_profile_settings",
        type_="unique",
    )
    op.drop_constraint(
        "tenant_business_profile_settings_tenant_code_key",
        "tenant_business_profile_settings",
        type_="unique",
    )

    op.create_check_constraint(
        "ck_tenant_tax_profile_effective_range",
        "tenant_tax_profile_settings",
        (
            "effective_to IS NULL OR "
            "(effective_from IS NOT NULL AND effective_to >= effective_from)"
        ),
    )
    op.create_check_constraint(
        "ck_tenant_business_profile_effective_range",
        "tenant_business_profile_settings",
        (
            "effective_to IS NULL OR "
            "(effective_from IS NOT NULL AND effective_to >= effective_from)"
        ),
    )

    # Najviše jedan open-ended/current red po tenantu.
    # Ovo obuhvata i legacy NULL/NULL red.
    op.create_index(
        "uq_tenant_tax_profile_open_period",
        "tenant_tax_profile_settings",
        ["tenant_code"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.create_index(
        "uq_tenant_business_profile_open_period",
        "tenant_business_profile_settings",
        ["tenant_code"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
    )

    # Lookup istorijskog perioda.
    op.create_index(
        "ix_tenant_tax_profile_effective_period",
        "tenant_tax_profile_settings",
        ["tenant_code", "effective_from", "effective_to"],
        unique=False,
    )
    op.create_index(
        "ix_tenant_business_profile_effective_period",
        "tenant_business_profile_settings",
        ["tenant_code", "effective_from", "effective_to"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_business_profile_effective_period",
        table_name="tenant_business_profile_settings",
    )
    op.drop_index(
        "ix_tenant_tax_profile_effective_period",
        table_name="tenant_tax_profile_settings",
    )

    op.drop_index(
        "uq_tenant_business_profile_open_period",
        table_name="tenant_business_profile_settings",
    )
    op.drop_index(
        "uq_tenant_tax_profile_open_period",
        table_name="tenant_tax_profile_settings",
    )

    op.drop_constraint(
        "ck_tenant_business_profile_effective_range",
        "tenant_business_profile_settings",
        type_="check",
    )
    op.drop_constraint(
        "ck_tenant_tax_profile_effective_range",
        "tenant_tax_profile_settings",
        type_="check",
    )

    op.drop_column(
        "tenant_business_profile_settings",
        "effective_to",
    )
    op.drop_column(
        "tenant_business_profile_settings",
        "effective_from",
    )
    op.drop_column(
        "tenant_tax_profile_settings",
        "effective_to",
    )
    op.drop_column(
        "tenant_tax_profile_settings",
        "effective_from",
    )

    # Downgrade pretpostavlja da istorijski dodatni redovi nisu prisutni.
    op.create_unique_constraint(
        "tenant_business_profile_settings_tenant_code_key",
        "tenant_business_profile_settings",
        ["tenant_code"],
    )
    op.create_unique_constraint(
        "tenant_tax_profile_settings_tenant_code_key",
        "tenant_tax_profile_settings",
        ["tenant_code"],
    )
