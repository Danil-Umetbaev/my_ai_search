from src.middleware.ai_capacity import run_model
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

        search_query = await run_model(
            self.llm.rewrite_query,
            question,
        )

        logger.info(
            "RAG rewrite | duration=%.2fs",
            perf_counter() - started,
        )

        if search_query.strip().upper() == "OFF_TOPIC":
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

        original_scores = await run_model(
            self.reranker.rerank,
            question,
            texts,
        )

        if same_query:
            scores = original_scores
        else:
            rewritten_scores = await run_model(
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

        if confidence < threshold:
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
            neighbors = await self.db.document_chunks.get_neigbors(
                best_chunk.document_id, best_chunk.chunk_index,
            )
            title, chunks = context_documents.setdefault(
                best_chunk.document_id, (best_chunk.document_title, {}),
            )
            for chunk in [best_chunk, *neighbors]:
                chunks[chunk.chunk_index] = chunk.content

        context_chunks = [
            f"Документ: {title}\n{self._join_chunks(chunks)}"
            for title, chunks in context_documents.values()
        ]
        context_size = sum(map(len, context_chunks))
        for index, document_id in enumerate(context_documents):
            document = await self.db.documents.get_one(id=document_id)
            if document.content:
                title, chunks = context_documents[document_id]
                scoped_text = f"Документ: {title}\n{self._context_excerpt(document.content, chunks)}"
                context_size += len(scoped_text) - len(context_chunks[index])
                context_chunks[index] = scoped_text
            if document.content and len(document.content) <= 3000:
                full_text = f"Документ: {document.title}\n{document.content}"
                size = context_size - len(context_chunks[index]) + len(full_text)
                if size <= 6000:
                    context_chunks[index] = full_text
                    context_size = size
        context = "\n\n---\n\n".join(context_chunks)

        logger.info(
            "RAG context | chunks=%s | chars=%s | duration=%.2fs",
            len(context_chunks),
            len(context),
            perf_counter() - started,
        )

        started = perf_counter()

        answer_llm = await run_model(
            self.llm.generate,
            question,
            search_query,
            context,
        )

        logger.info(
            "RAG generation | duration=%.2fs",
            perf_counter() - started,
        )

        if not answer_llm.answerable:
            return RAGResultSchema(
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=sources,
                confidence=confidence,
                used_chunks=used_chunks,
            )

        if getattr(answer_llm, "source_titles", None):
            sources = [source for source in sources if source.title in answer_llm.source_titles]
            selected_documents = {source.document_id for source in sources}
            selected_chunks = {chunk.chunk_id for chunk, _ in best_chunks if chunk.document_id in selected_documents}
            used_chunks = [chunk for chunk in used_chunks if chunk.chunk_id in selected_chunks]

        return RAGResultSchema(
            status=RAGStatus.ANSWERED,
            answer=answer_llm.answer,
            sources=sources,
            confidence=confidence,
            used_chunks=used_chunks,
        )

    @staticmethod
    def _context_excerpt(content: str, chunks: dict[int, str]) -> str:
        intervals = []
        for text in chunks.values():
            start = content.find(text)
            if start < 0 or content.find(text, start + 1) >= 0:
                return RAGService._join_chunks(chunks)
            end = start + len(text)
            line_start = content.rfind("\n", 0, start) + 1
            line_end = content.find("\n", end)
            if line_end < 0:
                line_end = len(content)
            if start - line_start <= 300:
                start = line_start
            if line_end - end <= 300:
                end = line_end
            intervals.append((start, end))
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1] + 2:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        headings = [heading for heading in re.finditer(r"(?m)^(#{1,6})\s+([^\n]+)$", content)
                    if content[:heading.start()].count("```") % 2 == 0]
        excerpts = []
        for start, end in merged:
            parents = []
            for heading in headings:
                if heading.start() > start:
                    break
                level = len(heading[1])
                while parents and parents[-1][0] >= level:
                    parents.pop()
                parents.append((level, heading[2]))
            path = " → ".join(title for _, title in parents)
            prefix = f"Раздел документа: {path}\n" if path else ""
            excerpts.append(prefix + content[start:end].strip())
        return "\n[… ]\n".join(excerpts)

    @staticmethod
    def _join_chunks(chunks: dict[int, str]) -> str:
        parts = []
        previous_index = None
        for index, text in sorted(chunks.items()):
            if parts and previous_index == index - 1:
                previous = parts[-1]
                overlap = next((size for size in range(min(len(previous), len(text)), 19, -1)
                                if previous.endswith(text[:size])), 0)
                if overlap:
                    parts[-1] += text[overlap:]
                else:
                    parts.append(text)
            else:
                parts.append(text)
            previous_index = index
        return "\n[… ]\n".join(parts)
