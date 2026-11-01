from uuid import UUID

from fastapi import APIRouter, Query, Response
from src.api.dependencies import AdminIdDep, AdminServiceDep
from src.schemas.admin import (
    Page,
    DocumentCreate,
    DocumentPatch,
    DocumentImport,
    UserCreate,
    UserPatch,
    ConversationCreate,
    ConversationPatch,
    EscalationCreate,
    EscalationPatch,
)
from src.schemas.users import User
from src.schemas.conversations import ConversationSchema
from src.schemas.documents import DocumentSchema, DocumentSummary
from src.schemas.escalations import EscalationSchema
from src.schemas.messages import MessageSchema
from src.exceptions import (
    NoUserFoundException,
    NoUserFoundHTTPException,
    NoConversationFoundException,
    NoConversationFoundHTTPException,
    NoDocumentFoundException,
    NoDocumentFoundHTTPException,
    NoEscalationFoundException,
    NoEscalationFoundHTTPException,
    AdminConflictException,
    AdminConflictHTTPException,
    AdminStorageException,
    AdminStorageHTTPException,
    DocumentImportException,
    DocumentImportHTTPException,
    DocumentIndexingException,
    DocumentIndexingHTTPException,
)

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@admin_router.get("/users", response_model=Page[User])
async def get_users(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await service.get_users(limit, offset)
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/users/{user_id}", response_model=User)
async def get_user(admin_id: AdminIdDep, service: AdminServiceDep, user_id: int):
    try:
        return await service.get_user_by_id(user_id)
    except NoUserFoundException as error:
        raise NoUserFoundHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.post("/users", response_model=User, status_code=201)
async def add_user(admin_id: AdminIdDep, service: AdminServiceDep, data: UserCreate):
    try:
        return await service.add_user(data)
    except NoUserFoundException as error:
        raise NoUserFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.patch("/users/{user_id}", response_model=User)
async def update_user(
    admin_id: AdminIdDep, service: AdminServiceDep, user_id: int, data: UserPatch
):
    try:
        return await service.update_user(user_id, data, admin_id)
    except NoUserFoundException as error:
        raise NoUserFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.delete("/users/{user_id}", response_class=Response, status_code=204)
async def delete_user(admin_id: AdminIdDep, service: AdminServiceDep, user_id: int):
    try:
        await service.delete_user(user_id, admin_id)
        return Response(status_code=204)
    except NoUserFoundException as error:
        raise NoUserFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/conversations", response_model=Page[ConversationSchema])
async def get_conversations(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await service.get_conversations(limit, offset)
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/conversations/{conversation_id}", response_model=ConversationSchema)
async def get_conversation(
    admin_id: AdminIdDep, service: AdminServiceDep, conversation_id: UUID
):
    try:
        return await service.get_conversation_by_id(conversation_id)
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.post("/conversations", response_model=ConversationSchema, status_code=201)
async def add_conversation(
    admin_id: AdminIdDep, service: AdminServiceDep, data: ConversationCreate
):
    try:
        return await service.add_conversation(data)
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.patch(
    "/conversations/{conversation_id}", response_model=ConversationSchema
)
async def update_conversation(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    conversation_id: UUID,
    data: ConversationPatch,
):
    try:
        return await service.update_conversation(conversation_id, data)
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.delete(
    "/conversations/{conversation_id}", response_class=Response, status_code=204
)
async def delete_conversation(
    admin_id: AdminIdDep, service: AdminServiceDep, conversation_id: UUID
):
    try:
        await service.delete_conversation(conversation_id)
        return Response(status_code=204)
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/escalations", response_model=Page[EscalationSchema])
async def get_escalations(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await service.get_escalations(limit, offset)
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/escalations/{escalation_id}", response_model=EscalationSchema)
async def get_escalation(
    admin_id: AdminIdDep, service: AdminServiceDep, escalation_id: UUID
):
    try:
        return await service.get_escalation_by_id(escalation_id)
    except NoEscalationFoundException as error:
        raise NoEscalationFoundHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.post("/escalations", response_model=EscalationSchema, status_code=201)
async def add_escalation(
    admin_id: AdminIdDep, service: AdminServiceDep, data: EscalationCreate
):
    try:
        return await service.add_escalation(data)
    except NoEscalationFoundException as error:
        raise NoEscalationFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error


@admin_router.patch("/escalations/{escalation_id}", response_model=EscalationSchema)
async def update_escalation(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    escalation_id: UUID,
    data: EscalationPatch,
):
    try:
        return await service.update_escalation(escalation_id, data)
    except NoEscalationFoundException as error:
        raise NoEscalationFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.delete(
    "/escalations/{escalation_id}", response_class=Response, status_code=204
)
async def delete_escalation(
    admin_id: AdminIdDep, service: AdminServiceDep, escalation_id: UUID
):
    try:
        await service.delete_escalation(escalation_id)
        return Response(status_code=204)
    except NoEscalationFoundException as error:
        raise NoEscalationFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/documents", response_model=Page[DocumentSummary])
async def get_documents(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await service.get_documents(limit, offset)
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get("/documents/{document_id}", response_model=DocumentSchema)
async def get_document(
    admin_id: AdminIdDep, service: AdminServiceDep, document_id: UUID
):
    try:
        return await service.get_document_by_id(document_id)
    except NoDocumentFoundException as error:
        raise NoDocumentFoundHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.post("/documents", response_model=DocumentSchema, status_code=201)
async def add_document(
    admin_id: AdminIdDep, service: AdminServiceDep, data: DocumentCreate
):
    try:
        return await service.add_document(data)
    except NoDocumentFoundException as error:
        raise NoDocumentFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error
    except DocumentIndexingException as error:
        raise DocumentIndexingHTTPException from error


@admin_router.patch("/documents/{document_id}", response_model=DocumentSchema)
async def update_document(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    document_id: UUID,
    data: DocumentPatch,
):
    try:
        return await service.update_document(document_id, data)
    except NoDocumentFoundException as error:
        raise NoDocumentFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error
    except DocumentIndexingException as error:
        raise DocumentIndexingHTTPException from error


@admin_router.delete(
    "/documents/{document_id}", response_class=Response, status_code=204
)
async def delete_document(
    admin_id: AdminIdDep, service: AdminServiceDep, document_id: UUID
):
    try:
        await service.delete_document(document_id)
        return Response(status_code=204)
    except NoDocumentFoundException as error:
        raise NoDocumentFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.get(
    "/conversations/{conversation_id}/messages", response_model=Page[MessageSchema]
)
async def get_conversation_messages(
    admin_id: AdminIdDep,
    service: AdminServiceDep,
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await service.get_messages_by_conversation_id(
            conversation_id, limit, offset
        )
    except NoConversationFoundException as error:
        raise NoConversationFoundHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error


@admin_router.post("/documents/import", response_model=DocumentSchema, status_code=201)
async def import_document(
    admin_id: AdminIdDep, service: AdminServiceDep, data: DocumentImport
):
    try:
        return await service.import_document(data)
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error
    except DocumentImportException as error:
        raise DocumentImportHTTPException from error
    except DocumentIndexingException as error:
        raise DocumentIndexingHTTPException from error


@admin_router.post("/documents/{document_id}/reindex", response_model=DocumentSchema)
async def reindex_document(
    admin_id: AdminIdDep, service: AdminServiceDep, document_id: UUID
):
    try:
        return await service.reindex_document(document_id)
    except NoDocumentFoundException as error:
        raise NoDocumentFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error
    except DocumentIndexingException as error:
        raise DocumentIndexingHTTPException from error


@admin_router.post("/documents/{document_id}/refresh", response_model=DocumentSchema)
async def refresh_document(
    admin_id: AdminIdDep, service: AdminServiceDep, document_id: UUID
):
    try:
        return await service.refresh_document(document_id)
    except NoDocumentFoundException as error:
        raise NoDocumentFoundHTTPException from error
    except AdminConflictException as error:
        raise AdminConflictHTTPException from error
    except AdminStorageException as error:
        raise AdminStorageHTTPException from error
    except DocumentIndexingException as error:
        raise DocumentIndexingHTTPException from error
    except DocumentImportException as error:
        raise DocumentImportHTTPException from error
