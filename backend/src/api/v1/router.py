from fastapi import APIRouter
from src.api.v1.health import health_router
from src.api.v1.conversations import conversation_router
from src.api.v1.chat import chat_router
router = APIRouter(prefix='/api/v1')

router.include_router(health_router)
router.include_router(conversation_router)
router.include_router(chat_router)
