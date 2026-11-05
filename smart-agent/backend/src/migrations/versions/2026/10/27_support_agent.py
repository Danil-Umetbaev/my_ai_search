from alembic import op

revision = "support_agent_01"
down_revision = "4e070d56b61e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE support_sessions (
        id uuid PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id),
        state jsonb NOT NULL DEFAULT '{}', history jsonb NOT NULL DEFAULT '[]',
        ticket_id uuid, created_at timestamptz NOT NULL DEFAULT now())""")
    op.execute(
        """CREATE TABLE support_tickets (
        id uuid PRIMARY KEY, session_id uuid NOT NULL UNIQUE REFERENCES support_sessions(id),
        user_id integer NOT NULL REFERENCES users(id), details jsonb NOT NULL,
        status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved')),
        resolution text NOT NULL DEFAULT '', assigned_to integer REFERENCES users(id),
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_session_ticket FOREIGN KEY(ticket_id) REFERENCES support_tickets(id)"
    )
    op.execute(
        "CREATE INDEX support_tickets_created ON support_tickets(created_at DESC)"
    )


def downgrade():
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_session_ticket")
    op.drop_table("support_tickets")
    op.drop_table("support_sessions")
