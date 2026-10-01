from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.embeddings.base import EmbeddingProvider
from src.schemas.vector_search import VectorSearchResultSchema

class VectorSearchService(BaseService):

    def __init__(self, db: DBManager | None = None, embedding: EmbeddingProvider | None =  None):
        super().__init__(db)
        self.embedding = embedding

    async def search(self, query: str, top_k: int=5) ->list[VectorSearchResultSchema]:
        if top_k <= 0:
            raise ValueError('Количество подходящих строк должно быть положительным')

        query_embedding = self.embedding.embed_query(query)

        return await self.db.document_chunks.search_similar(query_embedding, top_k)

