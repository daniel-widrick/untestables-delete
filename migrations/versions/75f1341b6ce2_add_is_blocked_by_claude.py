"""add is blocked by claude

Revision ID: 75f1341b6ce2
Revises: 41c40b3d0d6e
Create Date: 2025-06-17 18:16:53.782467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75f1341b6ce2'
down_revision: Union[str, None] = '41c40b3d0d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('repositories', sa.Column('is_blocked_by_claude', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'is_blocked_by_claude')
