import asyncio
import hashlib
from datetime import datetime, timezone
from src.models.enums import UserRole, Status
from src.exceptions import NotificationRetryException
from src.services.base import BaseService
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
    def __init__(
        self,
        db,
        indexer=None,
        source=None,
        indexer_factory=None,
        notification_provider=None,
    ):
        super().__init__(db)
        self.notification_provider = notification_provider
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
            return await self.db.users.get_one(id=user_id)
        except NoResultFoundException as error:
            raise NoUserFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def update_user(self, user_id, data, actor_id):
        try:
            existing = await self.db.users.get_one(id=user_id, for_update=True)
            values = data.model_dump(exclude_unset=True)
            if user_id == actor_id and (
                values.get("is_active") is False
                or ("role" in values and values["role"] != UserRole.admin)
            ):
                raise AdminConflictException
            if any(getattr(existing, key) != value for key, value in values.items()):
                values["token_version"] = existing.token_version + 1
            saved = await self.db.users.edit(values, id=user_id)
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

    async def get_conversations(self, limit=50, offset=0):
        try:
            return await self.db.conversations.get_page(limit, offset)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_conversation_by_id(self, conversation_id):
        try:
            return await self.db.conversations.get_one(id=conversation_id)
        except NoResultFoundException as error:
            raise NoConversationFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_escalations(self, limit=50, offset=0, work_status=None):
        try:
            return await self.db.escalations.get_page(
                limit, offset, **({"work_status": work_status} if work_status else {})
            )
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_escalation_by_id(self, escalation_id):
        try:
            return await self.db.escalations.get_one(id=escalation_id)
        except NoResultFoundException as error:
            raise NoEscalationFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def update_escalation(self, escalation_id, data):
        try:
            existing = await self.db.escalations.get_one(
                id=escalation_id, for_update=True
            )
            values = data.model_dump(exclude_unset=True)
            assignee = values.get("assigned_to", existing.assigned_to)
            state = values.get("work_status", existing.work_status)
            if assignee is not None:
                specialist = await self.db.users.get_one_or_none(id=assignee)
                if (
                    not specialist
                    or not specialist.is_active
                    or specialist.role not in {UserRole.admin, UserRole.it}
                ):
                    raise AdminConflictException
            if state == "in_progress" and assignee is None:
                raise AdminConflictException
            if (
                state in {"resolved", "closed"}
                and not values.get("resolution", existing.resolution).strip()
            ):
                raise AdminConflictException
            saved = await self.db.escalations.edit(values, id=escalation_id)
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

    async def get_documents(self, limit=50, offset=0, archived=False):
        try:
            return await self.db.documents.get_page(limit, offset, is_archived=archived)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_document_by_id(self, document_id):
        try:
            return await self.db.documents.get_one(id=document_id)
        except NoResultFoundException as error:
            raise NoDocumentFoundException from error
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_messages_by_conversation_id(
        self, conversation_id, limit=50, offset=0
    ):
        try:
            await self.db.conversations.get_one(id=conversation_id)
            return await self.db.messages.get_page_by_conversation_id(
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
                existing = await self.db.documents.get_one(
                    id=document_id, for_update=True
                )
            elif document is not None:
                existing = await self.db.documents.find_url(document.source_url)
                if existing is not None:
                    raise AdminConflictException
            if existing and existing.is_archived:
                raise AdminConflictException
            if document is None:
                values = existing.model_dump(exclude={"id", "is_archived"})
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
                saved = await self.db.documents.edit(values, id=existing.id)
            else:
                saved = await self.db.documents.add(values)
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

    async def archive_document(self, document_id):
        try:
            await self.db.documents.lock_catalog()
            await self.db.documents.get_one(id=document_id, for_update=True)
            saved = await self.db.documents.set_archived(document_id, True)
            await self.db.document_chunks.deactivate_document(document_id)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoDocumentFoundException from error
        except (DatabaseException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def restore_document(self, document_id):
        try:
            await self.db.documents.lock_catalog()
            current = await self.db.documents.get_one(id=document_id, for_update=True)
            if not current.is_archived:
                await self.db.commit()
                return current
            saved = await self.db.documents.set_archived(document_id, False)
            await self._index(saved)
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            await self.db.rollback()
            raise NoDocumentFoundException from error
        except (DatabaseException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminStorageException from error
        except BaseException:
            await self.db.rollback()
            raise

    async def retry_notification(self, escalation_id):
        try:
            current = await self.db.escalations.get_one(
                id=escalation_id, for_update=True
            )
            if current.status == Status.sent:
                raise AdminConflictException
            if self.notification_provider is None:
                raise NotificationRetryException
            try:
                await self.notification_provider.send_escalation(
                    question=current.question,
                    reason=current.reason,
                    conversation_id=current.conversation_id,
                    created_at=current.created_at,
                )
            except Exception as error:
                await self.db.escalations.edit(
                    {"status": Status.failed}, id=escalation_id
                )
                await self.db.commit()
                raise NotificationRetryException from error
            saved = await self.db.escalations.edit(
                {"status": Status.sent}, id=escalation_id
            )
            await self.db.commit()
            return saved
        except NoResultFoundException as error:
            raise NoEscalationFoundException from error
        except (DatabaseException, DataIntegrityException) as error:
            await self.db.rollback()
            raise AdminStorageException from error

    async def get_unanswered(self, limit=50, offset=0):
        try:
            return await self.db.messages.get_unanswered(limit, offset)
        except DatabaseException as error:
            raise AdminStorageException from error

    async def get_specialists(self):
        try:
            return await self.db.users.get_specialists()
        except DatabaseException as error:
            raise AdminStorageException from error
