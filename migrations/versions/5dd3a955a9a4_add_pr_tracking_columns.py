"""Add PR tracking columns

Revision ID: 5dd3a955a9a4
Revises: cba608fbd101
Create Date: 2025-06-13 15:46:22.063885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dd3a955a9a4'
down_revision: Union[str, None] = 'cba608fbd101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('repositories', sa.Column('pr_created', sa.Boolean(), nullable=True))
    op.add_column('repositories', sa.Column('pr_merged', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'pr_merged')
    op.drop_column('repositories', 'pr_created')
