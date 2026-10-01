from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.services.vector_search import VectorSearchService
from src.ai.llm.qwen import QwenLLMProvider
from src.services.rag import RAGService
from src.utils.db import DBManager
from src.database import async_session_maker
from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider
import asyncio

async def main():

    async with DBManager(async_session_maker) as db:
        qwen_provider = QwenEmbeddingProvider()
        llm = QwenLLMProvider()
        vector_search = VectorSearchService(db, qwen_provider)
        reranker = CrossEncoderRerankerProvider()
        rag_service = RAGService(vector_search, llm, reranker)

        question = "Что находилось вдали за горизонтом?"
        answer = await rag_service.answer(question, 10, 1, 0.5)
        print(answer)


        question = "Какого цвета был автомобиль?"
        answer = await rag_service.answer(question, 10, 1, 0.5)
        print(answer)

if __name__ == '__main__':
    asyncio.run(main())