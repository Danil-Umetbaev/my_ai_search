from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.llm.base import LLMProvider
from src.services.vector_search import VectorSearchService
import asyncio
class RAGService(BaseService):


    def __init__(self, search_service: VectorSearchService, llm: LLMProvider):
        self.vector_search = search_service
        self.llm = llm


    async def answer(self, question: str, top_k: int=5, threshhold: float = 0.5) -> str:

        chunks = await self.vector_search.search(question, top_k)
        chunks = [chunk for chunk in chunks if chunk.similarity > threshhold]
        if not chunks:
            return 'Информации недостаточно'

        chunks_content = '\n\n'.join(map(lambda x: x.content, chunks))

        answer_llm = await asyncio.to_thread(self.llm.generate, question, chunks_content)

        return answer_llm


