"""add invoice buyer type and tax id

Revision ID: 20260812_invoice_buyer_type
Revises: 20260812_invoice_discount
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_invoice_buyer_type"
down_revision: Union[str, None] = "20260812_invoice_discount"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "buyer_type",
            sa.String(length=16),
            nullable=False,
            server_default="UNSPECIFIED",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column("buyer_tax_id", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_invoices_buyer_type",
        "invoices",
        "buyer_type in ('BUSINESS','INDIVIDUAL','UNSPECIFIED')",
    )
    op.create_check_constraint(
        "ck_invoices_individual_without_tax_id",
        "invoices",
        "buyer_type != 'INDIVIDUAL' OR buyer_tax_id IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_invoices_individual_without_tax_id",
        "invoices",
        type_="check",
    )
    op.drop_constraint("ck_invoices_buyer_type", "invoices", type_="check")
    op.drop_column("invoices", "buyer_tax_id")
    op.drop_column("invoices", "buyer_type")
