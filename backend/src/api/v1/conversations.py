from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import text
from src.api.dependencies import check_optional_session, get_current_user_data
from src.schemas.messages import MessageSchema
from src.api.dependencies import ConversationServiceDep, DBDep
from src.schemas.conversations import ConversationSchema
from src.services.conversation import ConversationService
from src.exceptions import (
    NoConversationFoundHTTPException,
    NoConversationFoundException,
)

conversation_router = APIRouter(
    prefix="/conversations", dependencies=[Depends(check_optional_session)]
)


@conversation_router.post("")
async def add_conversation(
    conversation_service: ConversationServiceDep,
) -> ConversationSchema:
    return await conversation_service.create_conversation()


@conversation_router.get("/{conversation_id}/messages")
async def get_messages_by_conversation_id(
    conversation_service: ConversationServiceDep, conversation_id: UUID, request: Request
) -> list[MessageSchema]:
    try:
        state = await conversation_service.db.session.scalar(
            text("SELECT support_state FROM conversations WHERE id=:id"), {"id": conversation_id}
        )
        if state and state.get("_chat_owner") is not None:
            token = request.cookies.get("access_token")
            user = await get_current_user_data(conversation_service.db, token) if token else None
            if user is None or user.id != state["_chat_owner"]:
                raise HTTPException(404, "Диалог не найден")
        return await conversation_service.get_messages(conversation_id)
    except NoConversationFoundException:
        raise NoConversationFoundHTTPException
