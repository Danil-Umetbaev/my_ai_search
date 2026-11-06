from uuid import UUID

from src.models.documents import DocumentORM
from src.repositories.mappers.mappers import DocumentDataMapper
from src.repositories.base import BaseRepository
from src.schemas.documents import DocumentAddSchema, DocumentSchema


from sqlalchemy import select, update
from src.models.document_chunk import DocumentChunkORM

class DocumentRepository(BaseRepository):
    mapper = DocumentDataMapper
    model = DocumentORM

    async def retire_missing_sources(self, source_urls: list[str]) -> None:
        if not source_urls:
            raise ValueError('Cannot replace an index with an empty source list')
        obsolete = select(self.model.id).where(self.model.source_url.not_in(source_urls))
        await self.session.execute(
            update(DocumentChunkORM)
            .where(DocumentChunkORM.document_id.in_(obsolete))
            .values(is_active=False)
        )
        await self.session.execute(
            update(self.model)
            .where(self.model.source_url.not_in(source_urls))
            .values(is_archived=True)
        )


    async def update_by_id(
        self, document_id: UUID, document: DocumentAddSchema, exclude_unset=False
    ) -> DocumentSchema:
        return await self.edit(document, exclude_unset=exclude_unset, id=document_id)

    async def lock_catalog(self):
        from sqlalchemy import text

        await self._execute(text("SELECT pg_advisory_xact_lock(26110101)"))

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
            await self._execute(select(self.model).where(condition).limit(1))
        ).scalar_one_or_none()
        return self.mapper.map_to_domain_entity(row) if row else None

    async def get_page(self, limit=50, offset=0, **filter_by):
        from sqlalchemy import select, func
        from src.schemas.documents import DocumentSummary

        fields = [getattr(self.model, name) for name in DocumentSummary.model_fields]
        total = (
            await self._execute(
                select(func.count()).select_from(self.model).filter_by(**filter_by)
            )
        ).scalar_one()
        rows = (
            (
                await self._execute(
                    select(*fields)
                    .filter_by(**filter_by)
                    .order_by(self.model.updated_at.desc(), self.model.id)
                    .limit(limit)
                    .offset(offset)
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

    async def set_archived(self, document_id, archived):
        return await self.edit({"is_archived": archived}, id=document_id)
