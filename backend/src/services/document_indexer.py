import enum

from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.chunking.token import TokenChunker
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.schemas.document_chunks import DocumentChunkAddSchema, DocumentChunkSchema
from src.schemas.documents import DocumentSchema
class DocumentIndexerService(BaseService):

    def __init__(
            self, db: DBManager | None = None,
            chunker: TokenChunker | None = None,
            embedding_provider: QwenEmbeddingProvider | None = None          ):
        super().__init__(db)
        self.chunker = chunker
        self.embedding_provider = embedding_provider


    async def index_document(self, document: DocumentSchema):
        chunks = self.chunker.split(document.content)
        embeddings = self.embedding_provider.embed_document(chunks)

        documents_chunks = [
            DocumentChunkAddSchema(
                document_id=document.id,
                chunk_index=index,
                content=obj[0],
                embedding=obj[-1]
            )
            for index, obj in enumerate(zip(chunks, embeddings))
        ]

        await self.db.document_chunks.add_bulk(documents_chunks)
        await self.db.commit()


