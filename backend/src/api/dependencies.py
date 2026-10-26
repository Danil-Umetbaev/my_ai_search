from typing import Annotated
from functools import lru_cache
from fastapi import Depends, HTTPException, Request

from src.services.auth import AuthService
from src.exceptions import UserNotAuthenticatedHTTPException
from src.database import async_session_maker
from src.utils.db import DBManager
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.ai.llm.qwen import QwenLLMProvider
from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider
from src.services.rag import RAGService
from src.services.chat import ChatService
from src.services.vector_search import VectorSearchService
from src.notifications.vk import VKNotificationProvider
from src.notifications.base import NotificationProvider
from src.services.escalation import EscalationService
from src.services.conversation import ConversationService
from src.config import settings
from src.schemas.users import UserDepSchema

async def get_db():
    async with DBManager(async_session_maker) as db:
        yield db


DBDep = Annotated[DBManager, Depends(get_db)]



@lru_cache
def get_embedding_provider():
    return QwenEmbeddingProvider()

embeddingDep = Annotated[QwenEmbeddingProvider, Depends(get_embedding_provider)]


@lru_cache
def get_llm_provider():
    return QwenLLMProvider()

llmDep = Annotated[QwenLLMProvider, Depends(get_llm_provider)]

@lru_cache
def get_reranker_provider():
    return CrossEncoderRerankerProvider()

rerankerDep = Annotated[CrossEncoderRerankerProvider, Depends(get_reranker_provider)]


def get_rag_service(db: DBDep, embedding: embeddingDep, llm: llmDep, reranker: rerankerDep):
    vector_search = VectorSearchService(db, embedding)
    return RAGService(db, vector_search, llm, reranker)

rag_serviceDep = Annotated[RAGService, Depends(get_rag_service)]




@lru_cache
def get_notification_provider():
    if not settings.VK_TOKEN or not settings.VK_PEER_ID or not settings.VK_GROUP_ID:
        return None
    return VKNotificationProvider(
        settings.VK_TOKEN,
        settings.VK_PEER_ID,
        settings.VK_GROUP_ID,
        settings.VK_API_VERSION
    )

NotificationProviderDep = Annotated[NotificationProvider | None, Depends(get_notification_provider)]

def get_escalation_service(db: DBDep, notification_provider: NotificationProviderDep):
    return EscalationService(db, notification_provider)

EscalationServiceDep = Annotated[EscalationService, Depends(get_escalation_service)]
def get_chat_service(db: DBDep, rag_service: rag_serviceDep, escalation_service: EscalationServiceDep):
    return ChatService(db, rag_service, escalation_service)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_conversation_service(db: DBDep):
    return ConversationService(db)


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


def get_token(request: Request):
    access_token = request.cookies.get("access_token", None)
    if access_token is None:
        raise UserNotAuthenticatedHTTPException
    return access_token


def get_current_user_data(token: str = Depends(get_token)):
    data = AuthService().decode_jwt(token)
    return UserDepSchema(id=data['user_id'], role=data['role'])


UserDataDep = Annotated[UserDepSchema, Depends(get_current_user_data)]

def require_trusted_origin(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    origin = request.headers.get("origin")

    if origin not in settings.AUTH_TRUSTED_ORIGINS:
        raise HTTPException(
            status_code=403,
            detail="Недопустимый источник запроса",
        )