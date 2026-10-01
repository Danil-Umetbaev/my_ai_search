import asyncio

from src.utils.db import DBManager
from src.database import async_session_maker
from src.services.document_indexer import DocumentIndexerService
from src.ai.chunking.token import TokenChunker
from src.ai.embeddings.qwen import QwenEmbeddingProvider


async def main():
    async with DBManager(async_session_maker) as db:
        chunker = TokenChunker("Qwen/Qwen3-Embedding-0.6B", 100, 20)
        embadding = QwenEmbeddingProvider()
        document = await db.documents.get_one(id='35cfe624-7822-4edc-b617-f085223dda70')
        await DocumentIndexerService(db, chunker, embadding).index_document(document)

if __name__ == '__main__':
    asyncio.run(main())