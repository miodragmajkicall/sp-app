"""add is_paid flag to invoices

Revision ID: 20251128_add_is_paid_to_invoices
Revises: 7f1e2d3c4b5a
Create Date: 2025-11-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251128_add_is_paid_to_invoices"
down_revision = "7f1e2d3c4b5a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoices",
        sa.Column(
            "is_paid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # uklanjamo server_default nakon inicijalnog populisanja
    op.alter_column("invoices", "is_paid", server_default=None)


def downgrade():
    op.drop_column("invoices", "is_paid")
