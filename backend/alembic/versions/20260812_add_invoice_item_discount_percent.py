"""add invoice item discount percent

Revision ID: 20260812_invoice_discount
Revises: 522c4a40e121
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_invoice_discount"
down_revision: Union[str, None] = "522c4a40e121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_items",
        sa.Column(
            "discount_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_item_discount_percent_range",
        "invoice_items",
        "discount_percent >= 0 AND discount_percent < 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_item_discount_percent_range",
        "invoice_items",
        type_="check",
    )
    op.drop_column("invoice_items", "discount_percent")
