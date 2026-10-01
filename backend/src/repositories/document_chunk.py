from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import DocumentChunkMapper
from src.models.document_chunk import DocumentChunkORM
from src.schemas.vector_search import VectorSearchResultSchema
from sqlalchemy import select
class DocumentChunkRepository(BaseRepository):
    mapper = DocumentChunkMapper
    model = DocumentChunkORM


    async def search_similar(self, query_embedding: list[float], top_k: int) -> list[VectorSearchResultSchema]:
        distance = self.model.embedding.cosine_distance(query_embedding).label('distance')
        query = (select(self.model, distance)
                .order_by(distance)
                .limit(top_k))
        result_query = (await self.session.execute(query)).all()

        result_list = [
            VectorSearchResultSchema(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity= 1 - distance
            )
            for chunk, distance in result_query
        ]

        return result_list
    



