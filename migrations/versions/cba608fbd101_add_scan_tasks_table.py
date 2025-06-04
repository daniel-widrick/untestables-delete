"""add scan tasks table

Revision ID: cba608fbd101
Revises: cf74106402b5
Create Date: 2025-06-04 14:37:52.885785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cba608fbd101'
down_revision: Union[str, None] = 'cf74106402b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'scan_tasks',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('min_stars', sa.Integer(), nullable=True),
        sa.Column('max_stars', sa.Integer(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('progress', sa.JSON(), nullable=True),
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_scan_tasks_status', 'scan_tasks', ['status'])
    op.create_index('idx_scan_tasks_created_at', 'scan_tasks', ['created_at'])
    op.create_index('idx_scan_tasks_task_type_status', 'scan_tasks', ['task_type', 'status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_scan_tasks_task_type_status', 'scan_tasks')
    op.drop_index('idx_scan_tasks_created_at', 'scan_tasks')
    op.drop_index('idx_scan_tasks_status', 'scan_tasks')
    op.drop_table('scan_tasks')
