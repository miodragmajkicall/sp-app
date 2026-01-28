"""add invoices.note

Revision ID: 522c4a40e121
Revises: 4d1a9b8c2f10
Create Date: 2026-01-27 20:28:25.754895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "522c4a40e121"
down_revision: Union[str, None] = "4d1a9b8c2f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration was originally created with an empty upgrade() and may have been
    # marked as applied in alembic_version without changing the DB.
    # Make it safe to re-apply.
    op.execute("ALTER TABLE public.invoices ADD COLUMN IF NOT EXISTS note TEXT")


def downgrade() -> None:
    # Make it safe to rollback even if the column was never created.
    op.execute("ALTER TABLE public.invoices DROP COLUMN IF EXISTS note")
