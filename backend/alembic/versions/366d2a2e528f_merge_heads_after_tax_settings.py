"""merge heads after tax_settings

Revision ID: 366d2a2e528f
Revises: 7b4a1df0e9ab, f3c1a2b4c5d6
Create Date: 2025-12-12 08:54:56.043244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '366d2a2e528f'
down_revision: Union[str, None] = ('7b4a1df0e9ab', 'f3c1a2b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
