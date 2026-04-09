"""add task tracking fields to simulation_results

Revision ID: 001_add_task_fields
Revises:
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001_add_task_fields"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulation_results") as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.String(255), nullable=True, index=True))
        batch_op.add_column(sa.Column("progress", sa.Integer(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("simulation_results") as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("error_message")
        batch_op.drop_column("progress")
        batch_op.drop_column("task_id")
