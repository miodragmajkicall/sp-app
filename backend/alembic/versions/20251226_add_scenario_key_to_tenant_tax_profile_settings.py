"""add scenario_key to tenant_tax_profile_settings

Revision ID: 4d1a9b8c2f10
Revises: e7d40e94e391
Create Date: 2025-12-26

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4d1a9b8c2f10"
down_revision = "e7d40e94e391"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_tax_profile_settings",
        sa.Column("scenario_key", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_tax_profile_settings", "scenario_key")
