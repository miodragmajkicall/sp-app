"""tax_settings

Revision ID: f3c1a2b4c5d6
Revises: d0f5e534243c
Create Date: 2025-12-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3c1a2b4c5d6"
down_revision = "d0f5e534243c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_code",
            sa.String(length=64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("income_tax_rate", sa.Numeric(6, 4), nullable=False, server_default="0.10"),
        sa.Column("pension_contribution_rate", sa.Numeric(6, 4), nullable=False, server_default="0.18"),
        sa.Column("health_contribution_rate", sa.Numeric(6, 4), nullable=False, server_default="0.12"),
        sa.Column("unemployment_contribution_rate", sa.Numeric(6, 4), nullable=False, server_default="0.015"),
        sa.Column("flat_costs_rate", sa.Numeric(6, 4), nullable=False, server_default="0.30"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="BAM"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_code", name="uq_tax_settings_tenant_code"),
    )


def downgrade() -> None:
    op.drop_table("tax_settings")
