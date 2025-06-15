"""Add is_malicious column to repositories table

Revision ID: e4ecc4a181c8
Revises: 5dd3a955a9a4
Create Date: 2025-06-15 10:45:14.370656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4ecc4a181c8'
down_revision: Union[str, None] = '5dd3a955a9a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('repositories', sa.Column('is_malicious', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'is_malicious')
