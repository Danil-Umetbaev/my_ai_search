from typing import Annotated
from functools import lru_cache
from fastapi import Depends, HTTPException, Request

from src.models.enums import UserRole
from src.services.auth import AuthService
from src.services.admin import AdminService
from src.exceptions import (
    PermissionHTTPError,
    UserNotAuthenticatedHTTPException,
    SessionRevokedException,
    SessionRevokedHTTPException,
    AuthUnavailableException,
    AuthUnavailableHTTPException,
)
from src.database import async_session_maker
from src.utils.db import DBManager
from src.ai.embeddings.base import EmbeddingProvider
from src.ai.llm.base import LLMProvider
from src.ai.reranking.base import RerankerProvider
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
    from src.ai.embeddings.qwen import QwenEmbeddingProvider
    return QwenEmbeddingProvider()

embeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


@lru_cache
def get_llm_provider():
    from src.ai.llm.qwen import QwenLLMProvider
    return QwenLLMProvider()

llmDep = Annotated[LLMProvider, Depends(get_llm_provider)]


@lru_cache
def get_reranker_provider():
    from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider
    return CrossEncoderRerankerProvider()

rerankerDep = Annotated[RerankerProvider, Depends(get_reranker_provider)]


def get_rag_service(
    db: DBDep, embedding: embeddingDep, llm: llmDep, reranker: rerankerDep
):
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
        settings.VK_API_VERSION,
    )


NotificationProviderDep = Annotated[
    NotificationProvider | None, Depends(get_notification_provider)
]


def get_escalation_service(db: DBDep, notification_provider: NotificationProviderDep):
    return EscalationService(db, notification_provider)


EscalationServiceDep = Annotated[EscalationService, Depends(get_escalation_service)]


def get_chat_service(
    db: DBDep, rag_service: rag_serviceDep, escalation_service: EscalationServiceDep
):
    return ChatService(db, rag_service, escalation_service)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_conversation_service(db: DBDep):
    return ConversationService(db)


ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]


def get_token(request: Request):
    access_token = request.cookies.get("access_token", None)
    if access_token is None:
        raise UserNotAuthenticatedHTTPException
    return access_token


async def get_current_user_data(db: DBDep, token: str = Depends(get_token)):
    data = AuthService().decode_jwt(token)
    try:
        await AuthService(db).validate_session(data)
    except SessionRevokedException as error:
        raise SessionRevokedHTTPException from error
    except AuthUnavailableException as error:
        raise AuthUnavailableHTTPException from error
    return UserDepSchema(id=data["user_id"], role=data["role"])


UserDataDep = Annotated[UserDepSchema, Depends(get_current_user_data)]


def get_admin_id(user: UserDataDep):
    if user.role == UserRole.admin:
        return user.id
    raise PermissionHTTPError


AdminIdDep = Annotated[int, Depends(get_admin_id)]


def require_trusted_origin(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    origin = request.headers.get("origin")

    if origin not in settings.AUTH_TRUSTED_ORIGINS:
        raise HTTPException(
            status_code=403,
            detail="Недопустимый источник запроса",
        )


@lru_cache
def get_admin_chunker():
    from src.ai.chunking.token import TokenChunker

    return TokenChunker("Qwen/Qwen3-Embedding-0.6B", 120, 30)


def build_admin_indexer(db):
    from src.services.document_indexer import DocumentIndexerService

    return DocumentIndexerService(db, get_admin_chunker(), get_embedding_provider())


def get_admin_service(db: DBDep, notification: NotificationProviderDep):
    return AdminService(
        db, indexer_factory=build_admin_indexer, notification_provider=notification
    )


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


async def check_optional_session(request: Request, db: DBDep):
    token = request.cookies.get("access_token")
    if token:
        await get_current_user_data(db, token)
