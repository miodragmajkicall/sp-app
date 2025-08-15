"""cash entries

Revision ID: aa68d85d25cb
Revises: ccfd9a8fd57e
Create Date: 2025-08-15 11:23:37.983582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa68d85d25cb'
down_revision: Union[str, None] = 'ccfd9a8fd57e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
