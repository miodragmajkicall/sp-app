"""create cash_entries table

Revision ID: ccfd9a8fd57e
Revises: 0026328e0d28
Create Date: 2025-08-15 11:12:39.803553
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ccfd9a8fd57e"
down_revision: Union[str, None] = "0026328e0d28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Kreira tabelu cash_entries u skladu sa backend/app/models.py -> CashEntry.

    Bitno:
    - id: BIGINT autoincrement primary key
    - tenant_code: string, vežemo na tenants.code (ondelete CASCADE)
    - kind: ograničen na 'income' ili 'expense' preko CHECK constrainta
    - amount: Numeric(12,2)
    - description: Text, nullable
    """
    op.create_table(
        "cash_entries",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "tenant_code",
            sa.String(length=64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_cash_entries_tenant_date",
        "cash_entries",
        ["tenant_code", "entry_date"],
    )

    op.create_check_constraint(
        "ck_cash_entries_kind",
        "cash_entries",
        "kind IN ('income','expense')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_cash_entries_kind", "cash_entries", type_="check")
    op.drop_index("ix_cash_entries_tenant_date", table_name="cash_entries")
    op.drop_table("cash_entries")
