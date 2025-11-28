"""add input_invoice_id to invoice_attachments

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f7
Create Date: 2025-11-28 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nova kolona na invoice_attachments
    op.add_column(
        "invoice_attachments",
        sa.Column("input_invoice_id", sa.BigInteger(), nullable=True),
    )

    # FK ka input_invoices.id, sa ON DELETE SET NULL
    op.create_foreign_key(
        "fk_invoice_attachments_input_invoice_id",
        "invoice_attachments",
        "input_invoices",
        ["input_invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Prvo obrišemo FK, pa kolonu
    op.drop_constraint(
        "fk_invoice_attachments_input_invoice_id",
        "invoice_attachments",
        type_="foreignkey",
    )
    op.drop_column("invoice_attachments", "input_invoice_id")
