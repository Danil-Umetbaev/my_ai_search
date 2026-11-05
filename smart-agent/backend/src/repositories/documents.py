from uuid import UUID

from src.models.documents import DocumentORM
from src.repositories.mappers.mappers import DocumentDataMapper
from src.repositories.base import BaseRepository
from src.schemas.documents import DocumentAddSchema, DocumentSchema
from sqlalchemy import update
class DocumentRepository(BaseRepository):
    mapper = DocumentDataMapper
    model = DocumentORM


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