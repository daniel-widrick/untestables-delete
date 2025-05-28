"""Add language column to repositories table."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_language_column'
down_revision = 'add_last_scanned_at'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('repositories', sa.Column('language', sa.String(50), nullable=True))

def downgrade():
    op.drop_column('repositories', 'language') 