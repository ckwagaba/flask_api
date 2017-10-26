"""empty message

Revision ID: e49564fd4272
Revises: 80eb535e379d
Create Date: 2017-10-24 09:38:38.164432

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e49564fd4272'
down_revision = '80eb535e379d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'bucketlists', ['name'])
    op.create_unique_constraint(None, 'items', ['name'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'items', type_='unique')
    op.drop_constraint(None, 'bucketlists', type_='unique')
    # ### end Alembic commands ###
