import asyncio
import logging
import re
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

    @staticmethod
    def _merge_contents(chunks) -> str:
        result = ""

        for chunk in chunks:
            content = chunk.content

            if not content:
                continue

            if not result:
                result = content
                continue

            overlap = 0

            for size in range(min(len(result), len(content)), 0, -1):
                if result.endswith(content[:size]):
                    overlap = size
                    break

            if overlap:
                result += content[overlap:]
            else:
                result += "\n" + content

        return result

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

        def normalized_query(value: str) -> str:
            return " ".join(
                value.translate(str.maketrans("", "", '\"«»“”')).casefold().split()
            ).strip(" ?.!")

        comparison = re.fullmatch(
            r"чем\s+(.+?)\s+отлича(?:ется|ются)\s+от\s+(.+)",
            question.strip().rstrip("?.!"),
            flags=re.IGNORECASE,
        )
        first_query = comparison[1] if comparison else question
        second_query = comparison[2] if comparison else search_query
        if comparison:
            if len(second_query.split()) == 1 and len(first_query.split()) > 1:
                second_query += " " + first_query.split()[-1]
            first_query = "Что такое " + first_query
            second_query = "Что такое " + second_query
        same_query = normalized_query(first_query) == normalized_query(second_query)
        started = perf_counter()

        original_vector = await self.vector_search.search(
            first_query,
            candidate_k,
        )

        if same_query:
            rewritten_vector = original_vector
        else:
            rewritten_vector = await self.vector_search.search(
                second_query,
                candidate_k,
            )

        original_lexical = await self.db.document_chunks.search_lexical(
            first_query,
            lexical_k,
        )

        if same_query:
            rewritten_lexical = original_lexical
        else:
            rewritten_lexical = await self.db.document_chunks.search_lexical(
                second_query,
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

        started = perf_counter()
        windows = {}
        expanded_texts = {}
        texts = []

        neighbor_windows = await self.db.document_chunks.get_neighbors_bulk(
            [(chunk.document_id, chunk.chunk_index) for chunk in documents]
        )

        for candidate in documents:
            neighbors = neighbor_windows[(candidate.document_id, candidate.chunk_index)]

            window_by_index = {
                chunk.chunk_index: chunk
                for chunk in neighbors
                if chunk.document_id == candidate.document_id
            }
            window_by_index[candidate.chunk_index] = candidate

            window = sorted(
                window_by_index.values(),
                key=lambda chunk: chunk.chunk_index,
            )

            windows[candidate.chunk_id] = window

            content = self._merge_contents(window)
            text = f"Документ: {candidate.document_title}\n{content}"

            expanded_texts[candidate.chunk_id] = text
            texts.append(text)

        logger.info(
            "RAG candidate expansion | candidates=%s | chars=%s | duration=%.2fs",
            len(documents),
            sum(len(text) for text in texts),
            perf_counter() - started,
        )

        if comparison:
            def subject_words(text: str) -> list[str]:
                return [
                    re.sub(r"(?:ого|его|ый|ий|ой|ая|яя|ое|ее|ые|ие|ом|ым|им|ую|юю|а|я|ы|и|у|ю|е)$", "", word)
                    for word in text.casefold().split()
                ]

            def canonical_subject(query: str) -> str:
                subject = query.removeprefix("Что такое ")
                words = subject_words(subject)
                for text in texts:
                    for heading in re.findall(
                        r"(?<![\w-])[А-ЯЁ][а-яё-]+(?: [а-яё-]+){0,3}(?= [А-ЯЁ])",
                        text,
                    ):
                        if subject_words(heading) == words:
                            return "Что такое " + heading
                return query

            first_query = canonical_subject(first_query)
            second_query = canonical_subject(second_query)
            logger.info("RAG comparison | first=%r | second=%r", first_query, second_query)

        started = perf_counter()

        original_scores = await asyncio.to_thread(
            self.reranker.rerank,
            first_query,
            texts,
        )

        if same_query:
            scores = original_scores
        else:
            rewritten_scores = await asyncio.to_thread(
                self.reranker.rerank,
                second_query,
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
                "| title=%r | expanded_content=%r",
                rank,
                score,
                chunk.chunk_id,
                chunk.document_title,
                expanded_texts[chunk.chunk_id],
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

        if comparison and not same_query:
            comparison_chunks = {}
            for side_scores in (original_scores, rewritten_scores):
                index = max(range(len(documents)), key=side_scores.__getitem__)
                if side_scores[index] < threshold:
                    logger.info("RAG decision | reason=comparison_missing_evidence")
                    return RAGResultSchema(
                        status=RAGStatus.NOT_FOUND,
                        answer=None,
                        sources=[],
                        confidence=confidence,
                        used_chunks=[],
                    )
                chunk = documents[index]
                comparison_chunks[chunk.chunk_id] = (chunk, scores[index])
            best_chunks = list(comparison_chunks.values())

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
        context_documents = {}

        for best_chunk, _ in best_chunks:
            document_id = best_chunk.document_id

            if document_id not in context_documents:
                context_documents[document_id] = {
                    "title": best_chunk.document_title,
                    "chunks": {},
                }

            document_chunks = context_documents[document_id]["chunks"]

            for chunk in windows[best_chunk.chunk_id]:
                document_chunks[chunk.chunk_index] = chunk

        context_parts = []
        context_chunk_count = 0

        for document in context_documents.values():
            ordered_chunks = sorted(
                document["chunks"].values(),
                key=lambda chunk: chunk.chunk_index,
            )

            context_chunk_count += len(ordered_chunks)
            groups = []
            current_group = []

            for chunk in ordered_chunks:
                if (
                    current_group
                    and chunk.chunk_index != current_group[-1].chunk_index + 1
                ):
                    groups.append(current_group)
                    current_group = []

                current_group.append(chunk)

            if current_group:
                groups.append(current_group)

            for group in groups:
                content = self._merge_contents(group)
                context_parts.append(
                    f"Документ: {document['title']}\n{content}"
                )

        context = "\n\n---\n\n".join(context_parts)

        logger.info(
            "RAG context | chunks=%s | chars=%s | duration=%.2fs",
            context_chunk_count,
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
