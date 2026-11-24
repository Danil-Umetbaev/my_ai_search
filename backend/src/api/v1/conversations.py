from uuid import UUID

from fastapi import APIRouter, Depends, Request
from src.api.dependencies import (
    check_optional_session, get_current_user_data, ConversationServiceDep,
)
from src.schemas.messages import MessageSchema
from src.schemas.conversations import ConversationSchema
from src.exceptions import NoConversationFoundHTTPException, NoConversationFoundException


conversation_router = APIRouter(
    prefix="/conversations", dependencies=[Depends(check_optional_session)]
)


@conversation_router.post("")
async def add_conversation(
    conversation_service: ConversationServiceDep, request: Request,
) -> ConversationSchema:
    token = request.cookies.get("access_token")
    user = await get_current_user_data(conversation_service.db, token) if token else None
    return await conversation_service.create_conversation(user)


@conversation_router.get("/{conversation_id}/messages")
async def get_messages_by_conversation_id(
    conversation_service: ConversationServiceDep, conversation_id: UUID, request: Request,
) -> list[MessageSchema]:
    token = request.cookies.get("access_token")
    user = await get_current_user_data(conversation_service.db, token) if token else None
    try:
        return await conversation_service.get_messages(conversation_id, user)
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error
