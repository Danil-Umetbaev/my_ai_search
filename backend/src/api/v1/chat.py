from fastapi import APIRouter, Depends, Request
from src.api.dependencies import check_optional_session, get_current_user_data
from src.schemas.chat import ChatRequest, ChatResponse
from src.exceptions import (
    NoConversationFoundException,
    NoConversationFoundHTTPException,
    RAGProcessingException,
    RAGProcessingHTTPException,
)
from src.api.dependencies import ChatServiceDep

chat_router = APIRouter(
    prefix="/chat/messages", dependencies=[Depends(check_optional_session)]
)


@chat_router.post("")
async def send_message(
    chat_service: ChatServiceDep, request: ChatRequest, http_request: Request
) -> ChatResponse:
    try:
        token = http_request.cookies.get("access_token")
        user = await get_current_user_data(chat_service.db, token) if token else None
        return await chat_service.send_message(request, user=user)
    except NoConversationFoundException:
        raise NoConversationFoundHTTPException
    except RAGProcessingException:
        raise RAGProcessingHTTPException
