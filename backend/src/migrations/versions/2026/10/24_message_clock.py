from alembic import op
import sqlalchemy as sa

revision = "a2410msgclock"
down_revision = "a2410dialogue"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("messages", "created_at", server_default=sa.text("clock_timestamp()"))


def downgrade():
    op.alter_column("messages", "created_at", server_default=sa.text("now()"))
