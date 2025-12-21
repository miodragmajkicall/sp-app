# /home/miso/dev/sp-app/sp-app/backend/alembic/versions/20251221_add_app_constants_sets.py
"""add app_constants_sets

Revision ID: 8f2c1a9b7d31
Revises: 6c7a1f9e12aa
Create Date: 2025-12-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "8f2c1a9b7d31"
down_revision = "6c7a1f9e12aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_constants_sets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("jurisdiction", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("updated_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(effective_to is null) OR (effective_to >= effective_from)",
            name="ck_app_constants_sets_effective_range",
        ),
    )

    op.create_index(
        "ix_app_constants_sets_jurisdiction_effective_from",
        "app_constants_sets",
        ["jurisdiction", "effective_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_app_constants_sets_jurisdiction_effective_from", table_name="app_constants_sets")
    op.drop_table("app_constants_sets")
