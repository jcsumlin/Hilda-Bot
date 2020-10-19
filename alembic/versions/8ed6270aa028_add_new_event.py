"""Add new Event

Revision ID: 8ed6270aa028
Revises: b6b7bdd7f9db
Create Date: 2020-10-19 17:12:12.662067

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ed6270aa028'
down_revision = 'b6b7bdd7f9db'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('INSERT INTO special_events (name) VALUES ("Drawtober Event 2020")')


def downgrade():
    pass
