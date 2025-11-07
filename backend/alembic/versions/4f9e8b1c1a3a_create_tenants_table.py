"""create tenants table

Revision ID: 4f9e8b1c1a3a
Revises: b6a5c2a8c9f1
Create Date: 2025-11-07 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4f9e8b1c1a3a"
down_revision = "b6a5c2a8c9f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_unique_constraint("uq_tenants_code", "tenants", ["code"])


def downgrade() -> None:
    op.drop_constraint("uq_tenants_code", "tenants", type_="unique")
    op.drop_table("tenants")
