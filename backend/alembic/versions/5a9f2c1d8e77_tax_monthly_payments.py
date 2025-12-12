"""tax_monthly_payments

Revision ID: 5a9f2c1d8e77
Revises: 366d2a2e528f
Create Date: 2025-12-12
"""

from alembic import op
import sqlalchemy as sa

revision = "5a9f2c1d8e77"
down_revision = "366d2a2e528f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_monthly_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_code",
            sa.String(length=64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_code",
            "year",
            "month",
            name="uq_tax_monthly_payments_tenant_year_month",
        ),
    )


def downgrade() -> None:
    op.drop_table("tax_monthly_payments")
