from alembic import op
import sqlalchemy as sa

revision = "b261101admin"
down_revision = "4e070d56b61e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations",
        sa.Column(
            "title", sa.String(255), nullable=False, server_default="Новый диалог"
        ),
    )


def downgrade():
    op.drop_column("conversations", "title")
