"""create tax_yearly_results table

Revision ID: 7f1e2d3c4b5a
Revises: 4b2f9c8e3a10
Create Date: 2025-11-26 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f1e2d3c4b5a"
down_revision: Union[str, None] = "4b2f9c8e3a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Kreira tabelu tax_yearly_results:

    - jedan red po (tenant_code, year)
    - čuva zbirne vrijednosti godišnjeg obračuna
    - služi kao 'zaključan' rezultat za cijelu godinu
    """
    op.create_table(
        "tax_yearly_results",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "months_included",
            sa.Integer(),
            nullable=False,
        ),
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
            name="uq_tax_yearly_results_tenant_year",
        ),
    )

    op.create_index(
        "ix_tax_yearly_results_tenant_year",
        "tax_yearly_results",
        ["tenant_code", "year"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tax_yearly_results_tenant_year",
        table_name="tax_yearly_results",
    )
    op.drop_table("tax_yearly_results")
