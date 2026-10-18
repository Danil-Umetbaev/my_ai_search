from uuid import UUID

from fastapi import APIRouter
from src.schemas.messages import MessageSchema
from src.api.dependencies import ConversationServiceDep, DBDep
from src.schemas.conversations import ConversationSchema
from src.services.conversation import ConversationService
from src.exceptions import NoConversationFoundHTTPException, NoConversationFoundException
conversation_router = APIRouter(prefix='/conversations')


@conversation_router.post('')
async def add_conversation(conversation_service: ConversationServiceDep) -> ConversationSchema:
    return await conversation_service.create_conversation()


@conversation_router.get('/{conversation_id}/messages')
async def get_messages_by_conversation_id(
    conversation_service: ConversationServiceDep,
    conversation_id: UUID

) -> list[MessageSchema]:
    try:
        return await conversation_service.get_messages(conversation_id)
    except NoConversationFoundException:
        raise NoConversationFoundHTTPException
