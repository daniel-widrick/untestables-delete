"""add last_scanned_at column

Revision ID: add_last_scanned_at
Revises: 1982ee72d7c9
Create Date: 2024-03-21 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_last_scanned_at'
down_revision = '1982ee72d7c9'
branch_labels = None
depends_on = None

def upgrade():
    # Add last_scanned_at column with default value of current timestamp
    op.add_column('repositories', sa.Column('last_scanned_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))

def downgrade():
    # Remove last_scanned_at column
    op.drop_column('repositories', 'last_scanned_at') 