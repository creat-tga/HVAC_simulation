"""add load_result_id to simulation_results

Revision ID: 002_add_load_result_id
Revises: 001_add_task_fields
Create Date: 2026-04-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_add_load_result_id"
down_revision: Union[str, None] = "001_add_task_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulation_results") as batch_op:
        batch_op.add_column(
            sa.Column("load_result_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_simulation_results_load_result_id",
            "simulation_results",
            ["load_result_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("simulation_results") as batch_op:
        batch_op.drop_constraint(
            "fk_simulation_results_load_result_id", type_="foreignkey"
        )
        batch_op.drop_column("load_result_id")
