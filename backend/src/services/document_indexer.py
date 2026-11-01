import asyncio

from src.middleware.ai_capacity import run_model
from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.chunking.token import TokenChunker
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.schemas.document_chunks import DocumentChunkAddSchema
from src.schemas.documents import DocumentSchema


class DocumentIndexerService(BaseService):
    def __init__(
        self,
        db: DBManager | None = None,
        chunker: TokenChunker | None = None,
        embedding_provider: QwenEmbeddingProvider | None = None,
    ):
        super().__init__(db)
        self.chunker = chunker
        self.embedding_provider = embedding_provider

    async def index_document(self, document: DocumentSchema) -> int:
        if not document.content or not document.content.strip():
            raise ValueError("Cannot replace a document index with empty content")
        chunks = await asyncio.to_thread(self.chunker.split, document.content)
        if not chunks:
            raise ValueError("Document produced no chunks")
        embeddings = []
        for start in range(0, len(chunks), 8):
            batch = [
                f"Название документа: {document.title}\n{chunk}"
                for chunk in chunks[start : start + 8]
            ]
            embeddings.extend(
                await run_model(self.embedding_provider.embed_document, batch)
            )
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding count does not match the document chunks")
        rows = [
            DocumentChunkAddSchema(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=embedding,
            )
            for index, (chunk, embedding) in enumerate(
                zip(chunks, embeddings, strict=True)
            )
        ]
        await self.db.document_chunks.retire_by_document_id(document.id)
        await self.db.document_chunks.add_bulk(rows)
        return len(rows)
