from fastapi import APIRouter
from src.services.chat import ChatService
from src.schemas.messages import MessageAddRequestSchema, MessageSchema
from src.exceptions import NoConversationFoundException, NoConversationFoundHTTPException
from src.api.dependencies import DBDep
chat_router = APIRouter(prefix='/chat/messages')

@chat_router.post('')
async def send_message(db: DBDep, message: MessageAddRequestSchema) -> MessageSchema:
    try:
        return await ChatService(db).send_message(message)
    except NoConversationFoundException:
        raise NoConversationFoundHTTPException
