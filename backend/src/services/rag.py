from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.llm.base import LLMProvider
from src.services.vector_search import VectorSearchService
from src.ai.reranking.base import RerankerProvider
import asyncio
class RAGService(BaseService):


    def __init__(self, search_service: VectorSearchService, llm: LLMProvider, reranker: RerankerProvider):
        self.vector_search = search_service
        self.llm = llm
        self.reranker = reranker


    async def answer(self, question: str, candidate_k: int = 10, top_k: int=5, threshold: float=0.5) -> str:

        chunks = await self.vector_search.search(question, candidate_k)
        documents = [chunk.content for chunk in chunks if chunk.similarity > threshold]

        if not documents:
            return 'Информации недостаточно'

        scores = self.reranker.rerank(question, documents)

        chunks_with_scores = [(chunk, score) for chunk, score in zip(documents, scores)]
        chunks_with_scores = sorted(chunks_with_scores, key=lambda x: x[1], reverse=True)[:top_k]


        chunks_content = '\n\n'.join(map(lambda x: x[0], chunks_with_scores))

        answer_llm = await asyncio.to_thread(self.llm.generate, question, chunks_content)

        return answer_llm


