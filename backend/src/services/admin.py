import asyncio
import hashlib
from datetime import datetime, timezone
from src.services.base import BaseService
from src.services.auth import AuthService
from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
from src.schemas.documents import DocumentAddSchema
from src.schemas.admin import DocumentImport
from src.exceptions import (
    NoResultFoundException,
    ObjectAlreadyExistsException,
    DataIntegrityException,
    DatabaseException,
    NoUserFoundException,
    NoConversationFoundException,
    NoDocumentFoundException,
    NoEscalationFoundException,
    AdminConflictException,
    AdminStorageException,
    DocumentImportException,
    DocumentIndexingException,
)


class AdminService(BaseService):
    def __init__(self, db, indexer=None, source=None, indexer_factory=None):
        super().__init__(db)
        self.indexer = indexer
        self.indexer_factory = indexer_factory
        self.source = source or ConfluenceKnowledgeSource()

    async def get_users(self, limit=50, offset=0):
        try:
            return await self.db.users.get_page(limit, offset)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_user_by_id(self, user_id):
        try:
            return await self.db.users.get_admin(user_id)
        except NoResultFoundException as error:
            raise NoUserFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def add_user(self, data):
        try:
            values = data.model_dump(exclude_unset=False)
            if "password" in values:
                values["hashed_password"] = await asyncio.to_thread(
                    AuthService().hash_password, values.pop("password")
                )
            saved = await self.db.users.create_admin(values)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoUserFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def update_user(self, user_id, data, actor_id):
        try:
            values = data.model_dump(exclude_unset=True)
            if (
                user_id == actor_id
                and "role" in values
                and values["role"].value != "admin"
            ):
                raise AdminConflictException
            if "password" in values:
                values["hashed_password"] = await asyncio.to_thread(
                    AuthService().hash_password, values.pop("password")
                )
            saved = await self.db.users.update_admin(user_id, values)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoUserFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def delete_user(self, user_id, actor_id):
        try:
            if user_id == actor_id:
                raise AdminConflictException
            await self.db.users.delete_admin(user_id)
            await self.db.commit()
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoUserFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def get_conversations(self, limit=50, offset=0):
        try:
            return await self.db.conversations.get_page(limit, offset)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_conversation_by_id(self, conversation_id):
        try:
            return await self.db.conversations.get_admin(conversation_id)
        except NoResultFoundException as error:
            raise NoConversationFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def add_conversation(self, data):
        try:
            values = data.model_dump(exclude_unset=False)
            saved = await self.db.conversations.create_admin(values)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoConversationFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def update_conversation(self, conversation_id, data):
        try:
            values = data.model_dump(exclude_unset=True)
            saved = await self.db.conversations.update_admin(conversation_id, values)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoConversationFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def delete_conversation(self, conversation_id):
        try:
            await self.db.conversations.delete_admin(conversation_id)
            await self.db.commit()
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoConversationFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def get_escalations(self, limit=50, offset=0):
        try:
            return await self.db.escalations.get_page(limit, offset)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_escalation_by_id(self, escalation_id):
        try:
            return await self.db.escalations.get_admin(escalation_id)
        except NoResultFoundException as error:
            raise NoEscalationFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def add_escalation(self, data):
        try:
            values = data.model_dump(exclude_unset=False)
            await self.get_conversation_by_id(data.conversation_id)
            saved = await self.db.escalations.create_admin(values)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoEscalationFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def update_escalation(self, escalation_id, data):
        try:
            values = data.model_dump(exclude_unset=True)
            saved = await self.db.escalations.update_admin(escalation_id, values)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoEscalationFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def delete_escalation(self, escalation_id):
        try:
            await self.db.escalations.delete_admin(escalation_id)
            await self.db.commit()
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoEscalationFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def get_documents(self, limit=50, offset=0):
        try:
            return await self.db.documents.get_page(limit, offset)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_document_by_id(self, document_id):
        try:
            return await self.db.documents.get_admin(document_id)
        except NoResultFoundException as error:
            raise NoDocumentFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_messages_by_conversation_id(
        self, conversation_id, limit=50, offset=0
    ):
        try:
            await self.db.conversations.get_admin(conversation_id)
            return await self.db.messages.get_admin_messages(
                conversation_id, limit, offset
            )
        except NoResultFoundException as error:
            raise NoConversationFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def _fetch_document(self, url):
        try:
            canonical = DocumentImport(url=url).url
            document = await self.source.fetch(canonical)
            if (
                not document.content.strip()
                or len(document.content) > 300000
                or not document.title.strip()
                or len(document.title) > 512
            ):
                raise ValueError("Empty or oversized document")
            return document
        except Exception as error:
            raise DocumentImportException from error

    async def _index(self, saved):
        try:
            if self.indexer is None and self.indexer_factory is not None:
                self.indexer = await asyncio.to_thread(self.indexer_factory, self.db)
            if self.indexer is None:
                raise RuntimeError("Indexer dependency missing")
            await self.indexer.index_document(saved)
        except Exception as error:
            raise DocumentIndexingException from error

    async def _write_document(
        self, document=None, document_id=None, patch=None, force=False
    ):
        try:
            await self.db.documents.lock_catalog()
            existing = None
            if document_id is not None:
                existing = await self.db.documents.get_admin(document_id, lock=True)
            elif document is not None:
                existing = await self.db.documents.find_url(document.source_url)
                if existing is not None:
                    raise AdminConflictException
            if document is None:
                values = existing.model_dump(exclude={"id"})
                values.update(patch or {})
                document = DocumentAddSchema(**values)
            document.checksum = hashlib.sha256(
                document.content.encode("utf-8")
            ).hexdigest()
            if (
                existing
                and not force
                and existing.title == document.title
                and existing.content == document.content
            ):
                await self.db.commit()
                return existing
            values = document.model_dump()
            values["updated_at"] = datetime.now(timezone.utc)
            if existing:
                saved = await self.db.documents.update_admin(existing.id, values)
            else:
                saved = await self.db.documents.create_admin(values)
            await self._index(saved)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoDocumentFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error
        except BaseException:
            await self.db.rollback()
            raise

    async def add_document(self, data):
        document = DocumentAddSchema(
            **data.model_dump(), source_type="manual", checksum=""
        )
        return await self._write_document(document=document)

    async def import_document(self, data):
        document = await self._fetch_document(data.url)
        return await self._write_document(document=document)

    async def update_document(self, document_id, data):
        return await self._write_document(
            document_id=document_id, patch=data.model_dump(exclude_unset=True)
        )

    async def reindex_document(self, document_id):
        return await self._write_document(document_id=document_id, force=True)

    async def refresh_document(self, document_id):
        existing = await self.get_document_by_id(document_id)
        if existing.source_type != "confluence":
            raise AdminConflictException
        document = await self._fetch_document(existing.source_url)
        return await self._write_document(document=document, document_id=document_id)

    async def delete_document(self, document_id):
        try:
            await self.db.documents.lock_catalog()
            await self.db.documents.delete_admin(document_id)
            await self.db.commit()
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoDocumentFoundException from error
        except (ObjectAlreadyExistsException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminConflictException from error
        except DatabaseException as error:
            await self.db.rollback()
            raise AdminStorageException from error
