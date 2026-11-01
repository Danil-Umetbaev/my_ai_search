from uuid import UUID

from fastapi import APIRouter
from backend.src.services.admin import AdminService
from src.api.dependencies import AdminIdDep, DBDep
from src.models.enums import UserRole
from src.exceptions import (NoUserFoundException, NoUserFoundHTTPException, NoConversationFoundException,
                            NoConversationFoundHTTPException, NoDocumentFoundException,
                            NoDocumentFoundHTTPException, NoEscalationFoundException,
                            NoEscalationFoundHTTPException)

admin_router = APIRouter(prefix='/admin')

@admin_router.get('/conversations')
async def get_conversations(admin_id: AdminIdDep, db: DBDep):
    return await AdminService(db).get_conversations()

@admin_router.get('/conversations/{conversation_id}')
async def get_messages_by_conversation_by_id(admin_id: AdminIdDep, db: DBDep, conversation_id: UUID):
    return await AdminService(db).get_messages_by_conversation_id(conversation_id=conversation_id)

@admin_router.get('/documents')
async def get_documents(admin_id: AdminIdDep, db: DBDep):
    return await AdminService(db).get_documents()

@admin_router.get('/documents/{document_id}')
async def get_document_by_id(admin_id: AdminIdDep, db: DBDep, document_id: UUID):

    return await AdminService(db).get_document_by_id(document_id=document_id)

@admin_router.get('/escalations')
async def get_escalations(admin_id: AdminIdDep, db: DBDep):
    return await AdminService(db).get_escalations()

@admin_router.get('/escalations/{escalation_id}')
async def get_escalation_by_id(admin_id: AdminIdDep, db: DBDep, escalation_id: UUID):
    return await AdminService(db).get_escalation_by_id(escalation_id=escalation_id)


@admin_router.get('/users')
async def get_users(admin_id: AdminIdDep, db: DBDep):
    return await AdminService(db).get_users()

@admin_router.get('/users/{user_id}')
async def get_user_by_id(admin_id: AdminIdDep, db: DBDep, user_id: UUID):
    return await AdminService(db).get_user_by_id(user_id=user_id)

