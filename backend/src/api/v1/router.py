from fastapi import APIRouter, Depends
from src.api.dependencies import require_trusted_origin
from src.api.v1.health import health_router
from src.api.v1.conversations import conversation_router
from src.api.v1.chat import chat_router
from src.api.v1.auth import auth_router
router = APIRouter(prefix='/api/v1', dependencies=[Depends(require_trusted_origin)],)

router.include_router(health_router)
router.include_router(conversation_router)
router.include_router(chat_router)
router.include_router(auth_router)

