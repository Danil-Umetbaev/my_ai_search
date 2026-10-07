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
        rag_service = RAGService(db, vector_search, llm, reranker)

        # questions = [
        #     "Что находится в разделе 'Справочники'?",
        #     "Как создать отдел?",
        #     "Что такое штучный товар?",
        #     "Можно ли вернуть весовой товар?",
        #     "Как настроить ограничение продажи алкоголя по времени?",
        #     "Как настроить интерфейс кассового модуля?",
        #     "Не могу найти раздел карты, где он находится?",
        #     "Как отменить оплату после печати чека?",
        #     "Какие ограничения есть при работе кассы в режиме общепита?",
        #     "Как выбрать язык интерефейса?"
        # ]
        questions = [
            # есть ответ
            # "Что находится в разделе Справочники?",
            "Как отменить оплату после печати чека?",
            # "Какие ограничения есть при работе кассы в режиме общепита?",
            # "Как создать отдел?",

            # # ответа в базе быть не должно
            # "Как оформить отпуск сотруднику?",
            # "Какая зарплата у директора компании?",
            # "Как настроить Wi-Fi в офисе?",
            # "Как заказать корпоративное такси?",
        ]

        for question in questions:
            result = await rag_service.answer(question, 30, 5)
            print("STATUS:", result.status)
            print("ANSWER:", result.answer)

            for source in result.sources:
                print(
                    source.title,
                    source.url,
                    source.score
                )

if __name__ == '__main__':
    asyncio.run(main())