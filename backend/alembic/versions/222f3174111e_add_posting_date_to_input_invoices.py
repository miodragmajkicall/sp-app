"""Add posting_date to input_invoices

Revision ID: 222f3174111e
Revises: d0f5e534243c
Create Date: 2025-12-09 13:52:12.706263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '222f3174111e'
down_revision: Union[str, None] = 'd0f5e534243c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dodaj nove kolone na input_invoices

    # 1) posting_date – može biti null
    op.add_column(
        "input_invoices",
        sa.Column("posting_date", sa.Date(), nullable=True),
    )

    # 2) expense_category – može biti null
    op.add_column(
        "input_invoices",
        sa.Column("expense_category", sa.String(length=64), nullable=True),
    )

    # 3) is_tax_deductible – NOT NULL, za postojeće redove default = true
    op.add_column(
        "input_invoices",
        sa.Column(
            "is_tax_deductible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # 4) is_paid – NOT NULL, za postojeće redove default = false
    op.add_column(
        "input_invoices",
        sa.Column(
            "is_paid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # (opciono ali poželjno) ukloni server_default da se za nove redove
    # oslanjamo na app-level default iz SQLAlchemy modela
    op.alter_column("input_invoices", "is_tax_deductible", server_default=None)
    op.alter_column("input_invoices", "is_paid", server_default=None)


def downgrade() -> None:
    # Obrnuti redoslijed pri dropovanju kolona
    op.drop_column("input_invoices", "is_paid")
    op.drop_column("input_invoices", "is_tax_deductible")
    op.drop_column("input_invoices", "expense_category")
    op.drop_column("input_invoices", "posting_date")
