import asyncio
import logging
from time import perf_counter

from src.ai.llm.base import LLMProvider
from src.ai.reranking.base import RerankerProvider
from src.core.logging import log_execution_time
from src.schemas.rag import (
    RAGChunkSourceSchema,
    RAGResultSchema,
    RAGStatus,
    SourceSchema,
)
from src.services.base import BaseService
from src.services.vector_search import VectorSearchService
from src.utils.db import DBManager


logger = logging.getLogger(__name__)


class RAGService(BaseService):
    def __init__(
        self,
        db: DBManager,
        search_service: VectorSearchService,
        llm: LLMProvider,
        reranker: RerankerProvider,
    ):
        super().__init__(db)
        self.vector_search = search_service
        self.llm = llm
        self.reranker = reranker

    @log_execution_time("RAG")
    async def answer(
        self,
        question: str,
        candidate_k: int = 40,
        lexical_k: int = 20,
        top_k: int = 3,
        threshold: float = 0.30,
    ) -> RAGResultSchema:
        started = perf_counter()

        search_query = await asyncio.to_thread(
            self.llm.rewrite_query,
            question,
        )

        logger.info(
            "RAG rewrite | duration=%.2fs",
            perf_counter() - started,
        )
        logger.info(
            "RAG input | question=%r | rewrite=%r",
            question,
            search_query,
        )

        if search_query.strip().upper() == "OFF_TOPIC":
            logger.info("RAG decision | reason=off_topic")
            return RAGResultSchema(
                status=RAGStatus.OFF_TOPIC,
                answer=(
                    "Я могу помочь с вопросами по базе знаний компании. "
                    "Попробуйте задать вопрос по рабочим инструкциям, "
                    "процессам или SetRetail10."
                ),
                sources=[],
                confidence=None,
                used_chunks=[],
            )

        same_query = question == search_query
        started = perf_counter()

        original_vector = await self.vector_search.search(
            question,
            candidate_k,
        )

        if same_query:
            rewritten_vector = original_vector
        else:
            rewritten_vector = await self.vector_search.search(
                search_query,
                candidate_k,
            )

        original_lexical = await self.db.document_chunks.search_lexical(
            question,
            lexical_k,
        )

        if same_query:
            rewritten_lexical = original_lexical
        else:
            rewritten_lexical = await self.db.document_chunks.search_lexical(
                search_query,
                lexical_k,
            )

        all_candidates = (
            original_vector
            + rewritten_vector
            + original_lexical
            + rewritten_lexical
        )

        documents = list(
            {
                chunk.chunk_id: chunk
                for chunk in all_candidates
            }.values()
        )

        logger.info(
            "RAG retrieval | candidates=%s | same_query=%s | duration=%.2fs",
            len(documents),
            same_query,
            perf_counter() - started,
        )

        if not documents:
            logger.info("RAG decision | reason=no_candidates")
            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=None,
                used_chunks=[],
            )

        texts = [
            f"Документ: {chunk.document_title}\n{chunk.content}"
            for chunk in documents
        ]

        started = perf_counter()

        original_scores = await asyncio.to_thread(
            self.reranker.rerank,
            question,
            texts,
        )

        if same_query:
            scores = original_scores
        else:
            rewritten_scores = await asyncio.to_thread(
                self.reranker.rerank,
                search_query,
                texts,
            )

            scores = [
                max(original, rewritten)
                for original, rewritten in zip(
                    original_scores,
                    rewritten_scores,
                    strict=True,
                )
            ]

        chunks_with_scores = sorted(
            zip(documents, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )

        confidence = chunks_with_scores[0][1]

        logger.info(
            "RAG rerank | passes=%s | confidence=%.4f | duration=%.2fs",
            1 if same_query else 2,
            confidence,
            perf_counter() - started,
        )

        for rank, (chunk, score) in enumerate(
            chunks_with_scores[:5],
            start=1,
        ):
            logger.info(
                "RAG candidate | rank=%s | score=%.4f | chunk_id=%s "
                "| title=%r | content=%r",
                rank,
                score,
                chunk.chunk_id,
                chunk.document_title,
                chunk.content,
            )

        logger.info(
            "RAG threshold | confidence=%.4f | threshold=%.4f | passed=%s",
            confidence,
            threshold,
            confidence >= threshold,
        )

        if confidence < threshold:
            logger.info("RAG decision | reason=below_threshold")
            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=confidence,
                used_chunks=[],
            )

        relative_threshold = confidence * 0.70

        strong_chunks = [
            (chunk, score)
            for chunk, score in chunks_with_scores
            if score >= relative_threshold
        ]

        best_chunks = strong_chunks[:top_k]

        if not best_chunks:
            best_chunks = [chunks_with_scores[0]]

        used_chunks = []
        sources = []
        seen_documents = set()

        for chunk, score in best_chunks:
            logger.info(
                "RAG selected | chunk_id=%s | score=%.4f | title=%r",
                chunk.chunk_id,
                score,
                chunk.document_title,
            )

            used_chunks.append(
                RAGChunkSourceSchema(
                    chunk_id=chunk.chunk_id,
                    score=score,
                )
            )

            if chunk.document_id in seen_documents:
                continue

            seen_documents.add(chunk.document_id)

            sources.append(
                SourceSchema(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    title=chunk.document_title,
                    url=chunk.document_url,
                    score=score,
                )
            )

        started = perf_counter()
        context_chunks = []
        seen_context_chunks = set()

        for best_chunk, _ in best_chunks:
            neighbors = await self.db.document_chunks.get_neigbors(
                best_chunk.document_id,
                best_chunk.chunk_index,
            )

            window = list(neighbors)

            central_exists = any(
                chunk.document_id == best_chunk.document_id
                and chunk.chunk_index == best_chunk.chunk_index
                for chunk in window
            )

            if not central_exists:
                window.append(best_chunk)

            window.sort(key=lambda chunk: chunk.chunk_index)

            for chunk in window:
                key = (chunk.document_id, chunk.chunk_index)

                if key in seen_context_chunks:
                    continue

                seen_context_chunks.add(key)

                context_chunks.append(
                    f"Документ: {best_chunk.document_title}\n{chunk.content}"
                )

        context = "\n\n---\n\n".join(context_chunks)

        logger.info(
            "RAG context | chunks=%s | chars=%s | duration=%.2fs",
            len(context_chunks),
            len(context),
            perf_counter() - started,
        )
        logger.info("RAG full context | %r", context)

        started = perf_counter()

        answer_llm = await asyncio.to_thread(
            self.llm.generate,
            question,
            search_query,
            context,
        )

        logger.info(
            "RAG generation | duration=%.2fs",
            perf_counter() - started,
        )
        logger.info(
            "RAG output | answerable=%s | answer=%r",
            answer_llm.answerable,
            answer_llm.answer,
        )

        if not answer_llm.answerable:
            logger.info("RAG decision | reason=llm_not_answerable")
            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=sources,
                confidence=confidence,
                used_chunks=used_chunks,
            )

        logger.info("RAG decision | reason=answered")
        return RAGResultSchema(
            status=RAGStatus.ANSWERED,
            answer=answer_llm.answer,
            sources=sources,
            confidence=confidence,
            used_chunks=used_chunks,
        )