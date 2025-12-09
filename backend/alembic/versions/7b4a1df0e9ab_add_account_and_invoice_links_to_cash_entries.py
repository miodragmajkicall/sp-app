# /home/miso/dev/sp-app/sp-app/backend/alembic/versions/7b4a1df0e9ab_add_account_and_invoice_links_to_cash_entries.py
"""Add account and invoice links to cash_entries

Revision ID: 7b4a1df0e9ab
Revises: 222f3174111e
Create Date: 2025-12-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b4a1df0e9ab"
down_revision: Union[str, None] = "222f3174111e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # account kolona sa default vrijednošću 'cash' za postojeće redove
    op.add_column(
        "cash_entries",
        sa.Column(
            "account",
            sa.String(length=16),
            nullable=False,
            server_default="cash",
        ),
    )

    # opcionalne veze na izlaznu i ulaznu fakturu
    op.add_column(
        "cash_entries",
        sa.Column("invoice_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "cash_entries",
        sa.Column("input_invoice_id", sa.BigInteger(), nullable=True),
    )

    # FK ka invoices / input_invoices
    op.create_foreign_key(
        "fk_cash_entries_invoice_id_invoices",
        "cash_entries",
        "invoices",
        ["invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_cash_entries_input_invoice_id_input_invoices",
        "cash_entries",
        "input_invoices",
        ["input_invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # check constraint za account
    op.create_check_constraint(
        "ck_cash_entries_account",
        "cash_entries",
        "account in ('cash','bank')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cash_entries_input_invoice_id_input_invoices",
        "cash_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_cash_entries_invoice_id_invoices",
        "cash_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_cash_entries_account",
        "cash_entries",
        type_="check",
    )

    op.drop_column("cash_entries", "input_invoice_id")
    op.drop_column("cash_entries", "invoice_id")
    op.drop_column("cash_entries", "account")
