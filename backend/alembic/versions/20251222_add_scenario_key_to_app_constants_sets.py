# /home/miso/dev/sp-app/sp-app/backend/alembic/versions/20251222_add_scenario_key_to_app_constants_sets.py
"""add scenario_key to app_constants_sets

Revision ID: 20251222_add_scenario_key
Revises: 8f2c1a9b7d31
Create Date: 2025-12-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251222_add_scenario_key"
down_revision = "8f2c1a9b7d31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) add column nullable first (safe for existing rows)
    op.add_column(
        "app_constants_sets",
        sa.Column("scenario_key", sa.String(length=64), nullable=True),
    )

    # 2) backfill from payload.scenario_key if present, else default by jurisdiction
    op.execute(
        """
        UPDATE app_constants_sets
        SET scenario_key = COALESCE(
            NULLIF(payload->>'scenario_key', ''),
            CASE
                WHEN jurisdiction = 'RS' THEN 'rs_pausal'
                WHEN jurisdiction = 'FBiH' THEN 'fbih_knjige'
                WHEN jurisdiction = 'BD' THEN 'bd_knjige'
                ELSE 'unknown'
            END
        )
        WHERE scenario_key IS NULL
        """
    )

    # 3) enforce NOT NULL after backfill
    op.alter_column("app_constants_sets", "scenario_key", nullable=False)

    # 4) index for fast lookup per jurisdiction+scenario+date
    op.create_index(
        "ix_app_constants_sets_jur_scn_from",
        "app_constants_sets",
        ["jurisdiction", "scenario_key", "effective_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_app_constants_sets_jur_scn_from", table_name="app_constants_sets")
    op.drop_column("app_constants_sets", "scenario_key")
