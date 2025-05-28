"""add_missing_test_columns

Revision ID: 1982ee72d7c9
Revises: 0223a33bad8e
Create Date: 2025-05-28 16:26:00.897404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1982ee72d7c9'
down_revision: Union[str, None] = '0223a33bad8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('repositories', sa.Column('missing_test_directories', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('repositories', sa.Column('missing_test_files', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('repositories', sa.Column('missing_test_config_files', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('repositories', sa.Column('missing_cicd_configs', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('repositories', sa.Column('missing_readme_mentions', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'missing_readme_mentions')
    op.drop_column('repositories', 'missing_cicd_configs')
    op.drop_column('repositories', 'missing_test_config_files')
    op.drop_column('repositories', 'missing_test_files')
    op.drop_column('repositories', 'missing_test_directories')
