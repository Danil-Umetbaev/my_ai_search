from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.llm.base import LLMProvider
from src.services.vector_search import VectorSearchService
from src.ai.reranking.base import RerankerProvider
import asyncio
class RAGService(BaseService):


    def __init__(self, db: DBManager, search_service: VectorSearchService, llm: LLMProvider, reranker: RerankerProvider):
        self.vector_search = search_service
        self.llm = llm
        self.reranker = reranker
        self.db = db


    async def answer(self, question: str, candidate_k: int = 10, top_k: int=5, threshold: float=0.5) -> str:
        search_query = await asyncio.to_thread(
            self.llm.rewrite_query,
            question
        )
        print("QUESTION:", question)
        print("SEARCH QUERY:", search_query)

        original_chunks = await self.vector_search.search(
            question,
            candidate_k
        )

        rewritten_chunks = await self.vector_search.search(
            search_query,
            candidate_k
        )

        documents = list({
            chunk.chunk_id: chunk
            for chunk in original_chunks + rewritten_chunks
        }.values())

        texts = [f'{chunk.document_title}\n{chunk.content}' for chunk in documents]

        original_scores = self.reranker.rerank(
            question,
            texts
        )

        rewritten_scores = self.reranker.rerank(
            search_query,
            texts
        )

        scores = [
            max(original_score, rewritten_score)
            for original_score, rewritten_score
            in zip(original_scores, rewritten_scores)
]
        chunks_with_scores = [(chunk, score) for chunk, score in zip(documents, scores)]
        chunks_with_scores = sorted(
            chunks_with_scores,
            key=lambda x: x[1],
            reverse=True
        )
        best_chunks = chunks_with_scores[:top_k]

        for chunk, score in best_chunks:
            print(f"SCORE: {score}")
            print(f'DOCUMENT: {chunk.document_id}')
            print(f'CHUNK_id: {chunk.chunk_id}')
            print(f'CONTEXT: {chunk.content}')
        context_chunks = []
        seen = set()

        for chunk, score in best_chunks:
            neighbors = await self.db.document_chunks.get_neigbors(
                chunk.document_id,
                chunk.chunk_index
            )

            for neighbor in neighbors:
                key = (
                    neighbor.document_id,
                    neighbor.chunk_index
                )

                if key not in seen:
                    seen.add(key)

                    context_chunks.append(
                        f"Документ: {chunk.document_title}\n"
                        f"{neighbor.content}"
                    )

        best_context = '\n\n'.join(context_chunks)
        answer_llm = await asyncio.to_thread(self.llm.generate, question, search_query, best_context)

        return answer_llm