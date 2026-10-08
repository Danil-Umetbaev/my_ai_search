from fastapi import APIRouter
from src.schemas.chat import ChatRequest, ChatResponse
from src.exceptions import NoConversationFoundException, NoConversationFoundHTTPException
from src.api.dependencies import ChatServiceDep
import time
chat_router = APIRouter(prefix='/chat/messages')

@chat_router.post('')
async def send_message(chat_service: ChatServiceDep , request: ChatRequest) -> ChatResponse:
    try:
        start = time.perf_counter()
        response = await chat_service.send_message(request)
        end = time.perf_counter()
        elapsed_time = end - start
        print(f"Функция выполнила работу за {elapsed_time:.6f} секунд")
        return response
    except NoConversationFoundException:
        raise NoConversationFoundHTTPException
