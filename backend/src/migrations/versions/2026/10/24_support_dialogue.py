from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a2410dialogue"
down_revision = "3f3c94e0848a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("support_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("messages", sa.Column("response_meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column("messages", "response_meta")
    op.drop_column("conversations", "support_state")
