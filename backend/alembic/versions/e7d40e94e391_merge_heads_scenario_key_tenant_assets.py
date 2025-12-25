"""merge heads (scenario_key + tenant_assets)

Revision ID: e7d40e94e391
Revises: 20251222_add_scenario_key, 9c2a8b4f1d73
Create Date: 2025-12-25 21:12:01.308073
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7d40e94e391"
down_revision: Union[str, None] = ("20251222_add_scenario_key", "9c2a8b4f1d73")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
