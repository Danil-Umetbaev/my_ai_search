from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "support_workflow_02"
down_revision = "support_agent_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "support_sessions",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "support_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "support_tickets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_support_sessions_user", "support_sessions", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_support_tickets_user_status", "support_tickets", ["user_id", "status"]
    )
    op.create_table(
        "support_ticket_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Uuid(),
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_support_ticket_events_ticket",
        "support_ticket_events",
        ["ticket_id", "created_at"],
    )


def downgrade():
    op.drop_table("support_ticket_events")
    op.drop_index("ix_support_tickets_user_status", table_name="support_tickets")
    op.drop_index("ix_support_sessions_user", table_name="support_sessions")
    op.drop_column("support_tickets", "version")
    op.drop_column("support_sessions", "updated_at")
    op.drop_column("support_sessions", "version")
