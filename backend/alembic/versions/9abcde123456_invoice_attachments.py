"""invoice_attachments table

Revision ID: 9abcde123456
Revises: 8a9b0c1d2e3f
Create Date: 2025-11-28 12:00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9abcde123456"
down_revision = "8a9b0c1d2e3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_code"],
            ["tenants.code"],
            name="fk_invoice_attachments_tenant_code",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_invoice_attachments_invoice_id",
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_invoice_attachments_tenant_code",
        "invoice_attachments",
        ["tenant_code"],
    )
    op.create_index(
        "ix_invoice_attachments_invoice_id",
        "invoice_attachments",
        ["invoice_id"],
    )
    op.create_index(
        "ix_invoice_attachments_created_at",
        "invoice_attachments",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_attachments_created_at", table_name="invoice_attachments")
    op.drop_index("ix_invoice_attachments_invoice_id", table_name="invoice_attachments")
    op.drop_index("ix_invoice_attachments_tenant_code", table_name="invoice_attachments")
    op.drop_table("invoice_attachments")
