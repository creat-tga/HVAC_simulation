"""link energy simulation results to system schemes

Revision ID: 003_add_scheme_simulation_link
Revises: 002_add_load_result_id
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_add_scheme_simulation_link"
down_revision: Union[str, None] = "002_add_load_result_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulation_results") as batch_op:
        batch_op.add_column(sa.Column("scheme_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_simulation_results_scheme_id", ["scheme_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_simulation_results_scheme_id", "system_schemes",
            ["scheme_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("simulation_results") as batch_op:
        batch_op.drop_constraint("fk_simulation_results_scheme_id", type_="foreignkey")
        batch_op.drop_index("ix_simulation_results_scheme_id")
        batch_op.drop_column("scheme_id")