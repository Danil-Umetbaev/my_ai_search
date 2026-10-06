import asyncio

from src.services.vector_search import VectorSearchService
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider
from src.utils.db import DBManager
from src.database import async_session_maker

async def main():
    async with DBManager(async_session_maker) as db:

        reranker = CrossEncoderRerankerProvider()
        qwen_provider = QwenEmbeddingProvider()
        questions = [
            "Что находится в разделе 'Справочники'?",
            "Как создать отдел?",
            "Что такое штучный товар?",
            "Можно ли вернуть весовой товар?",
            "Как настроить ограничение продажи алкоголя по времени?",
        ]
        for question in questions:
            print(f'ВОПРОС: {question}')
            candidates_k = 10
            top_k = 2
            chunks = await VectorSearchService(db, qwen_provider).search(
                question, candidates_k
            )

            documents = [chunk.content for chunk in chunks]# if chunk.similarity > 0.5]

            if not documents:
                return 'Информации недостаточно'

            scores = reranker.rerank(question, documents)

            chunks_with_scores = [(chunk, score) for chunk, score in zip(documents, scores)]
            chunks_with_scores = sorted(chunks_with_scores, key=lambda x: x[1], reverse=True)[:top_k]
            for document, score in chunks_with_scores:
                print(f'SCORE: {score}')
                print(document)
                print('-' * 100)
            print('\n\n')

if __name__ == '__main__':
    asyncio.run(main())