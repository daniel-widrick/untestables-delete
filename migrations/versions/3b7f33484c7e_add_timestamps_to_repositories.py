"""add_timestamps_to_repositories

Revision ID: 3b7f33484c7e
Revises: add_language_column
Create Date: 2025-05-30 08:53:43.969089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b7f33484c7e'
down_revision: Union[str, None] = 'add_language_column'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('repositories', sa.Column('last_push_time', sa.DateTime(), nullable=True))
    op.add_column('repositories', sa.Column('last_metadata_update_time', sa.DateTime(), nullable=True))
    op.add_column('repositories', sa.Column('creation_time', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('repositories', 'creation_time')
    op.drop_column('repositories', 'last_metadata_update_time')
    op.drop_column('repositories', 'last_push_time')

