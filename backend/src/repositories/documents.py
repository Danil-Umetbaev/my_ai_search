from uuid import UUID

from src.models.documents import DocumentORM
from src.repositories.mappers.mappers import DocumentDataMapper
from src.repositories.base import BaseRepository
from src.schemas.documents import DocumentAddSchema, DocumentSchema
from sqlalchemy import update
from sqlalchemy import select
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


    async def update_by_id(self, document_id: UUID, document: DocumentAddSchema, exclude_unset=False) -> DocumentSchema:
        edit_model = (
            update(self.model)
            .filter_by(id=document_id)
            .values(**document.model_dump(exclude_unset=exclude_unset))
            .returning(self.model)
        )
        result = await self.session.execute(edit_model)
        document_orm = result.scalar_one()
        return self.mapper.map_to_domain_entity(document_orm)
