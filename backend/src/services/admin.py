from uuid import UUID
from backend.src.ai.embeddings.base import EmbeddingProvider
from src.ai.chunking.token import TokenChunker
from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
from src.schemas.documents import DocumentAddSchema
from src.services.base import BaseService
from src.services.document_indexer import DocumentIndexerService
from src.schemas.conversations import ConversationAddSchema
from src.schemas.messages import MessageSchema
from src.exceptions import NoDocumentFoundException, NoEscalationFoundException, NoResultFoundException, NoConversationFoundException, NoUserFoundException

class AdminService(BaseService):


    async def get_conversations(self):
        return await self.db.conversations.get_all()


    async def get_messages_by_conversation_id(self, conversation_id: UUID):
        try:
            return await self.db.messages.get_messages_by_conversation_id(conversation_id=conversation_id)
        except NoResultFoundException:
            raise NoConversationFoundException


    async def get_documents(self):
        return await self.db.documents.get_all()

    async def add_document(self, url: str, chunker: TokenChunker, embedding_provider: EmbeddingProvider):
        source = ConfluenceKnowledgeSource()
        indexer = DocumentIndexerService(self.db, chunker, embedding_provider)
        try:
            document = await source.fetch(url)
            existing = await self.db.documents.get_one_or_none(source_url=document.source_url)
            if existing and existing.checksum == document.checksum:
                return
            if existing:
                saved = await self.db.documents.update_by_id(document_id=existing.id, document=document)
            else:
                saved = await self.db.documents.add(document)
            await indexer.index_document(saved)
            await self.db.commit()
        except Exception as error:
            await self.db.rollback()


    async def get_document_by_id(self, document_id: UUID):
        try:
            return await self.db.documents.get_one(id=document_id)
        except NoResultFoundException:
            raise NoDocumentFoundException


    async def get_escalations(self):
        return await self.db.escalations.get_all()

    async def get_escalation_by_id(self, escalation_id: UUID):
        try:
            return await self.db.escalations.get_one(id=escalation_id)
        except NoResultFoundException:
            raise NoEscalationFoundException


    async def get_users(self):
        return await self.db.users.get_all()

    async def get_user_by_id(self, user_id: UUID):
        try:
            return await self.db.users.get_one(id=user_id)
        except NoResultFoundException:
            raise NoUserFoundException



