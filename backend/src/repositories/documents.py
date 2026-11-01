from uuid import UUID

from src.models.documents import DocumentORM
from src.repositories.mappers.mappers import DocumentDataMapper
from src.repositories.base import BaseRepository
from src.schemas.documents import DocumentAddSchema, DocumentSchema
from sqlalchemy import update


class DocumentRepository(BaseRepository):
    mapper = DocumentDataMapper
    model = DocumentORM

    async def update_by_id(
        self, document_id: UUID, document: DocumentAddSchema, exclude_unset=False
    ) -> DocumentSchema:
        edit_model = (
            update(self.model)
            .filter_by(id=document_id)
            .values(**document.model_dump(exclude_unset=exclude_unset))
            .returning(self.model)
        )
        result = await self.session.execute(edit_model)
        document_orm = result.scalar_one()
        return self.mapper.map_to_domain_entity(document_orm)

    async def lock_catalog(self):
        from sqlalchemy import text

        await self.execute_admin(text("SELECT pg_advisory_xact_lock(26110101)"))

    async def find_url(self, url):
        from sqlalchemy import select, or_

        condition = self.model.source_url == url
        if url.startswith(
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/"
        ):
            condition = or_(
                condition,
                self.model.source_url.startswith(
                    url.rstrip("/") + "/", autoescape=True
                ),
            )
        row = (
            await self.execute_admin(select(self.model).where(condition).limit(1))
        ).scalar_one_or_none()
        return self.mapper.map_to_domain_entity(row) if row else None

    async def get_page(self, limit=50, offset=0):
        from sqlalchemy import select, func
        from src.schemas.admin import DocumentSummary

        fields = [getattr(self.model, name) for name in DocumentSummary.model_fields]
        total = (
            await self.execute_admin(select(func.count()).select_from(self.model))
        ).scalar_one()
        rows = (
            (
                await self.execute_admin(
                    select(*fields).order_by(self.model.id).limit(limit).offset(offset)
                )
            )
            .mappings()
            .all()
        )
        return {
            "items": [DocumentSummary.model_validate(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def delete_admin(self, object_id):
        from sqlalchemy import delete, select
        from src.models.document_chunk import DocumentChunkORM
        from src.models.message_sources import MessageSourceORM
        from src.exceptions import DataIntegrityException

        await self.get_admin(object_id, lock=True)
        used = await self.execute_admin(
            select(MessageSourceORM.id)
            .join(DocumentChunkORM, MessageSourceORM.chunk_id == DocumentChunkORM.id)
            .where(DocumentChunkORM.document_id == object_id)
            .limit(1)
        )
        if used.first() is not None:
            raise DataIntegrityException
        await self.execute_admin(
            delete(DocumentChunkORM).where(DocumentChunkORM.document_id == object_id)
        )
        await super().delete_admin(object_id)
