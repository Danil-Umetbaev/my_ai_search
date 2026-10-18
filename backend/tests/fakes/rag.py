from src.schemas.rag import RAGResultSchema, RAGStatus


class AnsweredFakeRAGService:

    async def answer(self, question: str) -> RAGResultSchema:
        return RAGResultSchema(
            status=RAGStatus.ANSWERED,
            answer="Тестовый ответ из документации.",
            sources=[],
            confidence=0.95,
            used_chunks=[]
        )


class NotFoundFakeRAGService:

    async def answer(self, question: str) -> RAGResultSchema:
        return RAGResultSchema(
            status=RAGStatus.NOT_FOUND,
            answer=None,
            sources=[],
            confidence=0.10,
            used_chunks=[]
        )