import asyncio

from src.services.vector_search import VectorSearchService
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.utils.db import DBManager
from src.database import async_session_maker

async def main():
    async with DBManager(async_session_maker) as db:

        qwen_provider = QwenEmbeddingProvider()
        result = await VectorSearchService(db, qwen_provider).search(
            'Что находилось вдали за горизонтом?', 5
        )
        for obj in result:
            print('\n\n\n\n')
            print(f'Similarity: {obj.similarity}')
            print(f'Chunk index: {obj.chunk_index}')
            print(f'Content: {obj.content}')


if __name__ == '__main__':
    asyncio.run(main())