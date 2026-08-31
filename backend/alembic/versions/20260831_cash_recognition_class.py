"""Add recognition classification to cash entries

Revision ID: 20260831_cash_recognition_class
Revises: 20260827_output_payment_unique
Create Date: 2026-08-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260831_cash_recognition_class"
down_revision: Union[str, None] = "20260827_output_payment_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cash_entries",
        sa.Column("recognition_class", sa.String(length=32), nullable=True),
    )

    op.execute(
        """
        UPDATE cash_entries
        SET recognition_class = 'business_activity'
        WHERE invoice_id IS NULL
          AND input_invoice_id IS NULL
        """
    )

    op.create_check_constraint(
        "ck_cash_entries_recognition_class",
        "cash_entries",
        (
            "recognition_class IS NULL OR "
            "recognition_class IN ('business_activity','cash_only')"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cash_entries_recognition_class",
        "cash_entries",
        type_="check",
    )
    op.drop_column("cash_entries", "recognition_class")
