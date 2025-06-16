"""add_is_active_column

Revision ID: 41c40b3d0d6e
Revises: add_is_active_column
Create Date: 2025-06-15 20:31:42.077797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41c40b3d0d6e'
down_revision: Union[str, None] = 'e4ecc4a181c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
