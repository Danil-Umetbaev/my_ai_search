from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "customer_equipment_01"
down_revision = "4e070d56b61e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("manufacturer", sa.String(100), nullable=True))
    op.add_column("documents", sa.Column("equipment_models", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("documents", sa.Column("software_version", sa.String(100), nullable=True))
    op.add_column("documents", sa.Column("page_number", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("images", postgresql.JSONB(), nullable=False, server_default="[]"))


def downgrade():
    for column in ("images", "page_number", "software_version", "equipment_models", "manufacturer"):
        op.drop_column("documents", column)
