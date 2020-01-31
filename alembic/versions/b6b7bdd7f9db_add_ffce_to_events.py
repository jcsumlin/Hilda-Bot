"""add FFCE to events

Revision ID: b6b7bdd7f9db
Revises: 9953ac90f63d
Create Date: 2020-01-29 22:01:13.947344

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6b7bdd7f9db'
down_revision = '9953ac90f63d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('INSERT INTO special_events (name) VALUES ("Fandoms February Creativity Event")')


def downgrade():
    pass
