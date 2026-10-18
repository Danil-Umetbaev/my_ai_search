from src.services.base import BaseService
from src.utils.db import DBManager
from src.ai.llm.base import LLMProvider
from src.services.vector_search import VectorSearchService
from src.ai.reranking.base import RerankerProvider
from src.schemas.rag import (
    RAGResultSchema,
    RAGStatus,
    SourceSchema,
    RAGChunkSourceSchema,
)
from src.core.logging import log_execution_time

import asyncio
import logging


logger = logging.getLogger()


class RAGService(BaseService):

    def __init__(
        self,
        db: DBManager,
        search_service: VectorSearchService,
        llm: LLMProvider,
        reranker: RerankerProvider,
    ):
        self.vector_search = search_service
        self.llm = llm
        self.reranker = reranker
        self.db = db

    @log_execution_time("RAG")
    async def answer(
        self,
        question: str,
        candidate_k: int = 40,
        lexical_k: int = 20,
        top_k: int = 3,
        threshold: float = 0.30,
    ) -> RAGResultSchema:

        # ============================================================
        # 1. REWRITE
        # ============================================================

        search_query = await asyncio.to_thread(
            self.llm.rewrite_query,
            question,
        )

        print()
        print(">>> REWRITE")
        print(">>> ORIGINAL:", question)
        print(">>> SEARCH QUERY:", search_query)

        if (
            search_query
            .strip()
            .upper()
            == "OFF_TOPIC"
        ):
            return RAGResultSchema(
                answer=(
                    "Я могу помочь с вопросами по базе знаний компании. "
                    "Попробуйте задать вопрос по рабочим инструкциям, "
                    "процессам или SetRetail10."
                ),
                sources=[],
                confidence=None,
                status=RAGStatus.OFF_TOPIC,
            )

        # ============================================================
        # 2. VECTOR SEARCH
        # ============================================================

        original_vector = (
            await self.vector_search.search(
                question,
                candidate_k,
            )
        )

        rewritten_vector = (
            await self.vector_search.search(
                search_query,
                candidate_k,
            )
        )

        # ============================================================
        # 3. LEXICAL SEARCH
        #
        # Ищем точные термины напрямую в тексте.
        # ============================================================

        original_lexical = (
            await self.db.document_chunks
            .search_lexical(
                question,
                lexical_k,
            )
        )

        rewritten_lexical = (
            await self.db.document_chunks
            .search_lexical(
                search_query,
                lexical_k,
            )
        )

        # ============================================================
        # 4. UNION
        #
        # vector original
        # +
        # vector rewrite
        # +
        # lexical original
        # +
        # lexical rewrite
        #
        # Дубликаты удаляем по chunk_id.
        # ============================================================

        all_candidates = (
            original_vector
            + rewritten_vector
            + original_lexical
            + rewritten_lexical
        )

        documents = list({
            chunk.chunk_id: chunk
            for chunk in all_candidates
        }.values())

        print()
        print(">>> HYBRID SEARCH")

        print(
            ">>> VECTOR ORIGINAL:",
            len(original_vector),
        )

        print(
            ">>> VECTOR REWRITE:",
            len(rewritten_vector),
        )

        print(
            ">>> LEXICAL ORIGINAL:",
            len(original_lexical),
        )

        print(
            ">>> LEXICAL REWRITE:",
            len(rewritten_lexical),
        )

        print(
            ">>> UNIQUE CANDIDATES:",
            len(documents),
        )

        if not documents:

            print(
                ">>> NOT_FOUND REASON: "
                "HYBRID SEARCH"
            )

            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=None,
                used_chunks=[],
            )

        # ============================================================
        # 5. RERANK
        #
        # Архитектуру НЕ меняем:
        #
        # original query rerank
        # +
        # rewritten query rerank
        # ↓
        # max score
        # ============================================================

        texts = [
            (
                f"Документ: "
                f"{chunk.document_title}\n"
                f"{chunk.content}"
            )
            for chunk in documents
        ]

        original_scores = (
            await asyncio.to_thread(
                self.reranker.rerank,
                question,
                texts,
            )
        )

        rewritten_scores = (
            await asyncio.to_thread(
                self.reranker.rerank,
                search_query,
                texts,
            )
        )

        scores = [
            max(
                original_score,
                rewritten_score,
            )
            for (
                original_score,
                rewritten_score,
            )
            in zip(
                original_scores,
                rewritten_scores,
            )
        ]

        chunks_with_scores = list(
            zip(
                documents,
                scores,
            )
        )

        chunks_with_scores.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        confidence = (
            chunks_with_scores[0][1]
        )

        print()
        print(">>> RERANK TOP 10")

        for (
            position,
            (chunk, score),
        ) in enumerate(
            chunks_with_scores[:10],
            start=1,
        ):

            print(
                f">>> {position:02d}. "
                f"score={score:.4f} | "
                f"title={chunk.document_title} | "
                f"chunk={chunk.chunk_index}"
            )

        # ============================================================
        # 6. THRESHOLD
        #
        # Было: 0.55
        #
        # Но прямой правильный chunk:
        #
        # "Товарные полки – настройка правил..."
        #
        # reranker оценил примерно в 0.33.
        #
        # Поэтому стартовая экспериментальная граница = 0.30.
        # После evaluation её откалибруем.
        # ============================================================

        print()
        print(
            ">>> BEST SCORE:",
            round(
                confidence,
                4,
            ),
        )

        print(
            ">>> THRESHOLD:",
            threshold,
        )

        if confidence < threshold:

            print(
                ">>> NOT_FOUND REASON: "
                "THRESHOLD"
            )

            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=confidence,
                used_chunks=[],
            )

        # ============================================================
        # 7. СИЛЬНЫЕ CHUNKS
        # ============================================================

        relative_threshold = (
            confidence * 0.70
        )

        strong_chunks = [
            (
                chunk,
                score,
            )
            for (
                chunk,
                score,
            )
            in chunks_with_scores
            if score >= relative_threshold
        ]

        best_chunks = (
            strong_chunks[:top_k]
        )

        if not best_chunks:
            best_chunks = [
                chunks_with_scores[0]
            ]

        print()
        print(
            ">>> CONTEXT SCORE LIMIT:",
            round(
                relative_threshold,
                4,
            ),
        )

        print(
            ">>> SELECTED CHUNKS:"
        )

        for (
            position,
            (chunk, score),
        ) in enumerate(
            best_chunks,
            start=1,
        ):

            print(
                f">>> {position:02d}. "
                f"score={score:.4f} | "
                f"title={chunk.document_title} | "
                f"chunk={chunk.chunk_index}"
            )

        # ============================================================
        # 8. SOURCES
        # ============================================================

        used_chunks = []
        sources = []

        seen_documents = set()

        for (
            chunk,
            score,
        ) in best_chunks:

            used_chunks.append(
                RAGChunkSourceSchema(
                    chunk_id=chunk.chunk_id,
                    score=score,
                )
            )

            if (
                chunk.document_id
                in seen_documents
            ):
                continue

            seen_documents.add(
                chunk.document_id
            )

            sources.append(
                SourceSchema(
                    document_id=(
                        chunk.document_id
                    ),
                    chunk_id=(
                        chunk.chunk_id
                    ),
                    title=(
                        chunk.document_title
                    ),
                    url=(
                        chunk.document_url
                    ),
                    score=score,
                )
            )

        # ============================================================
        # 9. CONTEXT
        #
        # Каждый сильный chunk + соседние chunks ±1.
        # ============================================================

        context_chunks = []

        seen_context_chunks = set()

        for (
            best_chunk,
            score,
        ) in best_chunks:

            neighbors = (
                await self.db
                .document_chunks
                .get_neigbors(
                    best_chunk.document_id,
                    best_chunk.chunk_index,
                )
            )

            window = list(
                neighbors
            )

            central_exists = any(
                (
                    chunk.document_id
                    == best_chunk.document_id
                )
                and (
                    chunk.chunk_index
                    == best_chunk.chunk_index
                )
                for chunk in window
            )

            if not central_exists:
                window.append(
                    best_chunk
                )

            window.sort(
                key=lambda chunk:
                    chunk.chunk_index
            )

            for chunk in window:

                key = (
                    chunk.document_id,
                    chunk.chunk_index,
                )

                if (
                    key
                    in seen_context_chunks
                ):
                    continue

                seen_context_chunks.add(
                    key
                )

                context_chunks.append(
                    (
                        f"Документ: "
                        f"{best_chunk.document_title}\n"
                        f"{chunk.content}"
                    )
                )

        best_context = (
            "\n\n---\n\n".join(
                context_chunks
            )
        )

        print()
        print(">>> CONTEXT")

        print(
            ">>> CHUNKS:",
            len(context_chunks),
        )

        print(
            ">>> CHARS:",
            len(best_context),
        )

        print(
            ">>> PREVIEW:"
        )

        print(
            best_context[:2000]
        )

        # ============================================================
        # 10. LLM
        # ============================================================

        answer_llm = (
            await asyncio.to_thread(
                self.llm.generate,
                question,
                search_query,
                best_context,
            )
        )

        if not answer_llm.answerable:

            print()
            print(
                ">>> NOT_FOUND REASON: LLM"
            )

            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=sources,
                confidence=confidence,
                used_chunks=used_chunks,
            )

        print()
        print(
            ">>> RESULT: ANSWERED"
        )

        return RAGResultSchema(
            status=RAGStatus.ANSWERED,
            answer=answer_llm.answer,
            sources=sources,
            confidence=confidence,
            used_chunks=used_chunks,
        )