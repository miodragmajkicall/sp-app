"""Add tax treatment to cash entries

Revision ID: 20260831_cash_tax_treatment
Revises: 20260831_cash_recognition_class
Create Date: 2026-08-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260831_cash_tax_treatment"
down_revision: Union[str, None] = "20260831_cash_recognition_class"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cash_entries",
        sa.Column("tax_treatment", sa.String(length=32), nullable=True),
    )
    op.execute(
        """
        UPDATE cash_entries
        SET tax_treatment = 'unresolved'
        WHERE invoice_id IS NULL
          AND input_invoice_id IS NULL
          AND recognition_class = 'business_activity'
          AND kind = 'expense'
        """
    )
    op.create_check_constraint(
        "ck_cash_entries_tax_treatment",
        "cash_entries",
        (
            "tax_treatment IS NULL OR "
            "tax_treatment IN ('deductible','nondeductible','unresolved')"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cash_entries_tax_treatment",
        "cash_entries",
        type_="check",
    )
    op.drop_column("cash_entries", "tax_treatment")
