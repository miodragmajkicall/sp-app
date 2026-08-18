"""Enforce one cash payment per input invoice

Revision ID: 20260818_input_payment_unique
Revises: 20260813_invoice_issuer_snapshot
Create Date: 2026-08-18

"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260818_input_payment_unique"
down_revision: Union[str, None] = "20260813_invoice_issuer_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_cash_entries_input_invoice_id",
        "cash_entries",
        ["input_invoice_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cash_entries_input_invoice_id",
        "cash_entries",
        type_="unique",
    )