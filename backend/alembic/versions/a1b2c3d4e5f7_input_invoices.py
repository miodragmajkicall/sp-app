"""add input_invoices table

Revision ID: a1b2c3d4e5f7
Revises: 9abcde123456
Create Date: 2025-11-28 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "9abcde123456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "input_invoices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("supplier_name", sa.String(length=128), nullable=False),
        sa.Column("supplier_tax_id", sa.String(length=64), nullable=True),
        sa.Column("supplier_address", sa.String(length=256), nullable=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("total_base", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_vat", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="BAM"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_code"],
            ["tenants.code"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_code",
            "supplier_name",
            "invoice_number",
            name="uq_input_invoice_per_supplier_tenant",
        ),
    )


def downgrade() -> None:
    op.drop_table("input_invoices")
