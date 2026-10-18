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

    async def index_document(
        self,
        document: DocumentSchema,
    ) -> int:

        # ------------------------------------------------------------
        # 1. Проверяем, есть ли вообще текст
        # ------------------------------------------------------------

        if not document.content or not document.content.strip():
            print(
                f"ПУСТОЙ ДОКУМЕНТ, chunks не создаются: "
                f"{document.title}"
            )
            return 0

        # ------------------------------------------------------------
        # 2. Chunking
        # ------------------------------------------------------------

        chunks = self.chunker.split(
            document.content
        )

        # На всякий случай дополнительная защита.
        if not chunks:
            print(
                f"CHUNKER ВЕРНУЛ 0 CHUNKS: "
                f"{document.title}"
            )
            return 0

        # ------------------------------------------------------------
        # 3. Формируем тексты для embeddings
        #
        # title участвует в embedding,
        # но в content БД НЕ добавляется.
        # ------------------------------------------------------------

        embedding_texts = [
            (
                f"Название документа: {document.title}\n"
                f"{chunk}"
            )
            for chunk in chunks
        ]

        # ------------------------------------------------------------
        # 4. Embeddings
        # ------------------------------------------------------------

        embeddings = self.embedding_provider.embed_document(
            embedding_texts
        )

        # Дополнительная проверка.
        if not embeddings:
            print(
                f"EMBEDDING PROVIDER ВЕРНУЛ 0 EMBEDDINGS: "
                f"{document.title}"
            )
            return 0

        # ------------------------------------------------------------
        # 5. Подготавливаем chunks для БД
        # ------------------------------------------------------------

        document_chunks = [
            DocumentChunkAddSchema(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=embedding,
            )
            for index, (chunk, embedding)
            in enumerate(
                zip(chunks, embeddings)
            )
        ]

        if not document_chunks:
            print(
                f"НЕЧЕГО СОХРАНЯТЬ В document_chunks: "
                f"{document.title}"
            )
            return 0

        # ------------------------------------------------------------
        # 6. Сохраняем
        # ------------------------------------------------------------

        await self.db.document_chunks.add_bulk(
            document_chunks
        )

        return len(document_chunks)