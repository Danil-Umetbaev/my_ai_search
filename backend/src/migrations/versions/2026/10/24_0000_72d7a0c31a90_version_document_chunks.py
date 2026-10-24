"""Keep historical sources while replacing the searchable document index."""
from alembic import op
import sqlalchemy as sa

revision = "72d7a0c31a90"
down_revision = "3f3c94e0848a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_chunks", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_active_document_chunks", "document_chunks", ["document_id", "chunk_index"],
                    postgresql_where=sa.text("is_active"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM document_chunks WHERE NOT is_active)")).scalar():
        raise RuntimeError("Historical chunk versions exist; restore the pre-migration database backup to roll back safely.")
    op.drop_index("ix_active_document_chunks", table_name="document_chunks")
    op.drop_column("document_chunks", "is_active")
