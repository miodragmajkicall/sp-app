"""merge alembic heads

Revision ID: d0f5e534243c
Revises: 20251128_add_is_paid_to_invoices, b1c2d3e4f5a6
Create Date: 2025-12-02 20:57:49.127766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0f5e534243c'
down_revision: Union[str, None] = ('20251128_add_is_paid_to_invoices', 'b1c2d3e4f5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
