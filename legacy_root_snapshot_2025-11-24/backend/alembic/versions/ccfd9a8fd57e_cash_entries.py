"""cash entries

Revision ID: ccfd9a8fd57e
Revises: 0026328e0d28
Create Date: 2025-08-15 11:12:39.803553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccfd9a8fd57e'
down_revision: Union[str, None] = '0026328e0d28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cash_entries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        # vezujemo se na tenants.code jer je jedinstven i tip je string
        sa.Column("tenant_code", sa.String(length=64), sa.ForeignKey("tenants.code", ondelete="CASCADE"), nullable=False),

        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),  # 'income' ili 'expense'
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Koristan indeks za listanje po klijentu i datumu
    op.create_index(
        "ix_cash_entries_tenant_date",
        "cash_entries",
        ["tenant_code", "entry_date"]
    )

    # (opciono) ograničimo vrijednosti za kind
    op.create_check_constraint(
        "ck_cash_entries_kind",
        "cash_entries",
        "kind IN ('income','expense')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_cash_entries_kind", "cash_entries", type_="check")
    op.drop_index("ix_cash_entries_tenant_date", table_name="cash_entries")
    op.drop_table("cash_entries")
