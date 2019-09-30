"""create inktober column

Revision ID: 9953ac90f63d
Revises: 
Create Date: 2019-09-29 17:37:17.983008

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9953ac90f63d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    special_events = op.create_table('special_events',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
    )
    op.add_column('content', sa.Column('event_id', sa.Integer))
    op.add_column('user', sa.Column('special_event_submitted', sa.Boolean))
    op.bulk_insert(special_events,
        [
            {'id':1, 'name':'Pride 2019'},
            {'id':2, 'name':'Inktober 2019'},
        ],
        multiinsert=False
    )
    op.execute('UPDATE content SET event_id = 1 WHERE content.pride = 1')
    with op.batch_alter_table("content") as batch_op:
        batch_op.drop_column('pride')
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column('pridesubmitted')

def downgrade():
    op.add_column('content', sa.Column('pride', sa.Boolean))
    op.add_column('user', sa.Column('pridesubmitted', sa.Boolean))
    op.execute('UPDATE content SET pride = 1 WHERE content.event_id = 1')
    with op.batch_alter_table("content") as batch_op:
        batch_op.drop_column('event_id')
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column('special_event_submitted')
    op.drop_table('special_events')
