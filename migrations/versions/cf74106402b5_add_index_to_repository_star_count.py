"""add_index_to_repository_star_count

Revision ID: cf74106402b5
Revises: 3b7f33484c7e
Create Date: 2025-05-30 14:01:24.313257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf74106402b5'
down_revision: Union[str, None] = '3b7f33484c7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(op.f('ix_repositories_star_count'), 'repositories', ['star_count'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_repositories_star_count'), table_name='repositories')
