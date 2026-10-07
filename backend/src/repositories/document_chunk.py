from src.models.documents import DocumentORM
from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import DocumentChunkMapper
from src.models.document_chunk import DocumentChunkORM
from src.schemas.document_chunks import DocumentChunkSchema
from src.schemas.vector_search import VectorSearchResultSchema
from sqlalchemy import delete, select
from uuid import UUID
class DocumentChunkRepository(BaseRepository):
    mapper = DocumentChunkMapper
    model = DocumentChunkORM


    async def search_similar(self, query_embedding: list[float], top_k: int) -> list[VectorSearchResultSchema]:
        distance = self.model.embedding.cosine_distance(query_embedding).label('distance')
        query = (select(self.model, distance, DocumentORM.title, DocumentORM.source_url)
                .join(DocumentORM, self.model.document_id == DocumentORM.id)
                .order_by(distance)
                .limit(top_k))
        result_query = (await self.session.execute(query)).all()

        result_list = [
            VectorSearchResultSchema(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity= 1 - distance,
                document_title=document_title,
                document_url=document_url
            )
            for chunk, distance, document_title, document_url in result_query
        ]

        return result_list

    async def get_neigbors(
            self,
            document_id: UUID,
            chunk_index: int,
            radius: int = 1,
    ) -> list[DocumentChunkSchema]:

        indexes = list(range(
            max(0, chunk_index - radius),
            chunk_index + radius + 1
        ))
        query = (select(self.model)
                 .filter_by(document_id=document_id)
                 .filter(self.model.chunk_index.in_(indexes))
                 .order_by(self.model.chunk_index))

        result_query = (await self.session.execute(query)).scalars().all()
        return [self.mapper.map_to_domain_entity(obj) for obj in result_query]


    async def get_by_document_id(
        self,
        document_id: UUID
    ) -> list[DocumentChunkSchema]:
        query = (select(self.model)
                 .filter_by(document_id=document_id)
                 .order_by(self.model.chunk_index))

        result_query = (await self.session.execute(query)).scalars().all()
        return [self.mapper.map_to_domain_entity(obj) for obj in result_query]


    async def delete_by_document_id(self, document_id: UUID) -> None:
        query = (delete(self.model)
                 .where(self.model.document_id==document_id))

        await self.session.execute(query)
