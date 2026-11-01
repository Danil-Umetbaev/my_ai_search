from alembic import op
import sqlalchemy as sa

revision = "b261101flows"
down_revision = "b261101admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "is_archived", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "escalations",
        sa.Column("work_status", sa.String(20), nullable=False, server_default="new"),
    )
    op.add_column("escalations", sa.Column("assigned_to", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_escalations_assigned_to",
        "escalations",
        "users",
        ["assigned_to"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "escalations",
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
    )
    op.create_check_constraint(
        "ck_escalations_work_status",
        "escalations",
        "work_status IN ('new', 'in_progress', 'resolved', 'closed')",
    )


def downgrade():
    op.drop_constraint("ck_escalations_work_status", "escalations", type_="check")
    op.drop_column("escalations", "resolution")
    op.drop_constraint("fk_escalations_assigned_to", "escalations", type_="foreignkey")
    op.drop_column("escalations", "assigned_to")
    op.drop_column("escalations", "work_status")
    op.drop_column("documents", "is_archived")
    op.drop_column("users", "token_version")
    op.drop_column("users", "is_active")
