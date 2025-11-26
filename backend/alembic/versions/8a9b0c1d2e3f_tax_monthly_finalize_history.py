"""tax monthly finalize history audit log

Revision ID: 8a9b0c1d2e3f
Revises: 7f1e2d3c4b5a
Create Date: 2025-11-26 20:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8a9b0c1d2e3f"
down_revision = "7f1e2d3c4b5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_monthly_finalize_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("total_income", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_expense", sa.Numeric(14, 2), nullable=False),
        sa.Column("taxable_base", sa.Numeric(14, 2), nullable=False),
        sa.Column("income_tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("contributions_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="BAM"),
        sa.Column("action", sa.String(length=32), nullable=False, server_default="finalize"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("triggered_by", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_code"],
            ["tenants.code"],
            name="fk_tax_monthly_finalize_history_tenant_code",
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_tax_monthly_finalize_history_tenant_year_month",
        "tax_monthly_finalize_history",
        ["tenant_code", "year", "month"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tax_monthly_finalize_history_tenant_year_month",
        table_name="tax_monthly_finalize_history",
    )
    op.drop_table("tax_monthly_finalize_history")
