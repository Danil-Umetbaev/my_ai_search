from fastapi import APIRouter
from src.schemas.chat import ChatRequest, ChatResponse
from src.exceptions import NoConversationFoundException, NoConversationFoundHTTPException, RAGProcessingException, RAGProcessingHTTPException
from src.api.dependencies import ChatServiceDep


chat_router = APIRouter(prefix='/chat/messages')

@chat_router.post('')
async def send_message(chat_service: ChatServiceDep , request: ChatRequest) -> ChatResponse:
    try:
        return await chat_service.send_message(request)
    except NoConversationFoundException:
        raise NoConversationFoundHTTPException
    except RAGProcessingException:
        raise RAGProcessingHTTPException