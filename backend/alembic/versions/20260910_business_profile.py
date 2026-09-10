"""Add tenant business profile settings.

Revision ID: 20260910_business_profile
Revises: 20260831_cash_tax_treatment
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_business_profile"
down_revision: Union[str, None] = "20260831_cash_tax_treatment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_business_profile_settings",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "tenant_code",
            sa.String(length=64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("sales_locations_count", sa.Integer(), nullable=True),
        sa.Column("sells_to_consumers", sa.Boolean(), nullable=True),
        sa.Column(
            "daily_cash_turnover_covered_elsewhere",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "has_noncash_sales_to_legal_entities",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "sales_locations_count IS NULL OR sales_locations_count >= 0",
            name="ck_tenant_business_profile_sales_locations_count",
        ),
    )


def downgrade() -> None:
    op.drop_table("tenant_business_profile_settings")
