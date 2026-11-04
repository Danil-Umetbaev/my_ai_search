from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import text

from src.api.dependencies import DBDep, UserDataDep
from src.schemas.support import (
    SupportMessage,
    SupportReply,
    TicketStatus,
    TicketSummary,
    TicketUpdate,
)
from src.services.support_dialogue import SupportDialogueService

support_router = APIRouter(prefix="/support", tags=["support"])


@support_router.get("/status")
async def support_status(db: DBDep, user: UserDataDep, request: Request):
    await SupportDialogueService(db).role(user.id)
    status = getattr(request.app.state, "models", {}).get("status", "loading")
    knowledge_ready = await db.session.scalar(
        text("SELECT EXISTS (SELECT 1 FROM document_chunks WHERE is_active)")
    )
    return {
        "models": status,
        "engine": "llm" if status == "ready" else "rules",
        "knowledge_ready": knowledge_ready,
    }


@support_router.post("/sessions", status_code=201)
async def create_session(db: DBDep, user: UserDataDep):
    return await SupportDialogueService(db).create(user.id)


@support_router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, db: DBDep, user: UserDataDep):
    return await SupportDialogueService(db).get(session_id, user.id)


@support_router.post("/sessions/{session_id}/messages", response_model=SupportReply)
async def message(
    session_id: UUID,
    data: SupportMessage,
    db: DBDep,
    user: UserDataDep,
    request: Request,
):
    return await SupportDialogueService(db).send(
        session_id, user.id, data, getattr(request.app.state, "models", {})
    )


@support_router.get("/tickets", response_model=list[TicketSummary])
async def tickets(
    db: DBDep,
    user: UserDataDep,
    queue: bool = False,
    status: TicketStatus | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await SupportDialogueService(db).list_tickets(
        user.id, queue, status, offset, limit
    )


@support_router.get("/tickets/{ticket_id}")
async def ticket(ticket_id: UUID, db: DBDep, user: UserDataDep):
    return await SupportDialogueService(db).ticket(ticket_id, user.id)


@support_router.patch("/tickets/{ticket_id}", response_model=TicketSummary)
async def update(ticket_id: UUID, data: TicketUpdate, db: DBDep, user: UserDataDep):
    return await SupportDialogueService(db).update_ticket(ticket_id, user.id, data)
