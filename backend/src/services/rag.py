from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.llm.base import LLMProvider
from src.services.vector_search import VectorSearchService
from src.ai.reranking.base import RerankerProvider
from src.schemas.rag import RAGResultSchema, RAGStatus, SourceSchema
import asyncio
class RAGService(BaseService):


    def __init__(self, db: DBManager, search_service: VectorSearchService, llm: LLMProvider, reranker: RerankerProvider):
        self.vector_search = search_service
        self.llm = llm
        self.reranker = reranker
        self.db = db


    async def answer(self, question: str, candidate_k: int = 10, top_k: int=5, threshold: float=0.8) -> RAGResultSchema:
        search_query = await asyncio.to_thread(
            self.llm.rewrite_query,
            question
        )

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

        if not documents:
            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=None,
            )

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
        confidence = chunks_with_scores[0][1]
        print("QUESTION:", question)
        print("CONFIDENCE:", confidence)
        if confidence < threshold:
            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=confidence,
            )
        best_chunks = chunks_with_scores[:top_k]

        sources = []
        seen_documents = set()
        context_chunks = []
        seen_chunks = set()

        for chunk, score in best_chunks:
            if chunk.document_id not in seen_documents:
                seen_documents.add(chunk.document_id)
                sources.append(
                        SourceSchema(
                            document_id=chunk.document_id,
                            chunk_id=chunk.chunk_id,
                            title=chunk.document_title,
                            url=chunk.document_url,
                            score=score
                        )
                )
            neighbors = await self.db.document_chunks.get_neigbors(
                chunk.document_id,
                chunk.chunk_index
            )



            for neighbor in neighbors:
                key = (
                    neighbor.document_id,
                    neighbor.chunk_index
                )
                if key in seen_chunks:
                    continue
                seen_chunks.add(key)
                context_chunks.append(
                        f"Документ: {chunk.document_title}\n"
                        f"{neighbor.content}"
                    )

        best_context = '\n\n'.join(context_chunks)
        answer_llm = await asyncio.to_thread(self.llm.generate, question, search_query, best_context)

        return RAGResultSchema(
                status=RAGStatus.ANSWERED,
                answer=answer_llm,
                sources=sources,
                confidence=confidence,
            )