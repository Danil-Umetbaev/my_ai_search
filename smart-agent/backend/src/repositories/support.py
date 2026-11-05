import json
from uuid import uuid4

from sqlalchemy import text


class SupportRepository:
    def __init__(self, session):
        self.session = session

    async def one(self, query, params):
        row = (await self.session.execute(text(query), params)).mappings().first()
        return dict(row) if row else None

    async def role(self, user_id):
        return await self.session.scalar(
            text("SELECT role::text FROM users WHERE id=:id"), {"id": user_id}
        )

    async def create_session(self, user_id):
        return await self.one(
            "INSERT INTO support_sessions (id, user_id) VALUES (:id, :user) RETURNING *",
            {"id": uuid4(), "user": user_id},
        )

    async def get_session(self, session_id, user_id, lock=False):
        query = "SELECT * FROM support_sessions WHERE id=:id AND user_id=:user"
        if lock:
            query += " FOR UPDATE"
        return await self.one(query, {"id": session_id, "user": user_id})

    async def save_session(self, session_id, state, history, ticket_id):
        return await self.one(
            "UPDATE support_sessions SET state=CAST(:state AS jsonb), history=CAST(:history AS jsonb), ticket_id=:ticket, version=version+1, updated_at=now() WHERE id=:id RETURNING *",
            {
                "id": session_id,
                "state": json.dumps(state, ensure_ascii=False),
                "history": json.dumps(history, ensure_ascii=False),
                "ticket": ticket_id,
            },
        )

    async def create_ticket(self, session_id, user_id, details):
        return await self.one(
            "INSERT INTO support_tickets (id, session_id, user_id, details) VALUES (:id, :session, :user, CAST(:details AS jsonb)) RETURNING *",
            {
                "id": uuid4(),
                "session": session_id,
                "user": user_id,
                "details": json.dumps(details, ensure_ascii=False),
            },
        )

    async def list_tickets(self, user_id, status, offset, limit):
        rows = await self.session.execute(
            text(
                "SELECT * FROM support_tickets WHERE (CAST(:user AS integer) IS NULL OR user_id=:user) AND (CAST(:status AS text) IS NULL OR status=:status) ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset"
            ),
            {"user": user_id, "status": status, "offset": offset, "limit": limit},
        )
        return [dict(row) for row in rows.mappings()]

    async def get_ticket(self, ticket_id, lock=False):
        return await self.one(
            "SELECT * FROM support_tickets WHERE id=:id"
            + (" FOR UPDATE" if lock else ""),
            {"id": ticket_id},
        )

    async def ticket_history(self, session_id):
        return await self.session.scalar(
            text("SELECT history FROM support_sessions WHERE id=:id"),
            {"id": session_id},
        )

    async def update_ticket(self, ticket_id, status, resolution, assigned_to):
        return await self.one(
            "UPDATE support_tickets SET status=:status, resolution=:resolution, assigned_to=:assigned, updated_at=now(), version=version+1 WHERE id=:id RETURNING *",
            {
                "id": ticket_id,
                "status": status,
                "resolution": resolution,
                "assigned": assigned_to,
            },
        )

    async def add_event(self, ticket_id, actor_id, payload):
        await self.session.execute(
            text(
                "INSERT INTO support_ticket_events (id, ticket_id, actor_id, payload) VALUES (:id, :ticket, :actor, CAST(:payload AS jsonb))"
            ),
            {
                "id": uuid4(),
                "ticket": ticket_id,
                "actor": actor_id,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )

    async def events(self, ticket_id):
        rows = await self.session.execute(
            text(
                "SELECT id, actor_id, payload, created_at FROM support_ticket_events WHERE ticket_id=:id ORDER BY created_at, id"
            ),
            {"id": ticket_id},
        )
        return [dict(row) for row in rows.mappings()]
