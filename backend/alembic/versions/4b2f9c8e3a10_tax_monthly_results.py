"""create tax_monthly_results table

Revision ID: 4b2f9c8e3a10
Revises: 1c90358a3b6c
Create Date: 2025-11-25 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b2f9c8e3a10"
down_revision: Union[str, None] = "1c90358a3b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Kreira tabelu tax_monthly_results:

    - jedan red po (tenant_code, year, month)
    - čuva sve izračunate vrijednosti iz mjesečnog obračuna
    - služi kao 'zaključan' rezultat koji se više ne računa automatski
    """
    op.create_table(
        "tax_monthly_results",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column(
            "total_income",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "total_expense",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "taxable_base",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "income_tax",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "contributions_total",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "total_due",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default="BAM",
        ),
        sa.Column(
            "is_final",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_code"],
            ["tenants.code"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_code",
            "year",
            "month",
            name="uq_tax_monthly_results_tenant_year_month",
        ),
    )

    op.create_index(
        "ix_tax_monthly_results_tenant_year_month",
        "tax_monthly_results",
        ["tenant_code", "year", "month"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tax_monthly_results_tenant_year_month",
        table_name="tax_monthly_results",
    )
    op.drop_table("tax_monthly_results")
