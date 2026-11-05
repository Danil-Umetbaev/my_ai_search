import re
from uuid import UUID

from sqlalchemy import (
    case,
    delete,
    func,
    literal,
    or_,
    select,
    update,
)

from src.models.documents import DocumentORM
from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import DocumentChunkMapper
from src.models.document_chunk import DocumentChunkORM
from src.models.message_sources import MessageSourceORM
from src.schemas.document_chunks import DocumentChunkSchema
from src.schemas.vector_search import VectorSearchResultSchema


class DocumentChunkRepository(BaseRepository):

    mapper = DocumentChunkMapper
    model = DocumentChunkORM

    LEXICAL_STOP_WORDS = {
        "в",
        "во",
        "на",
        "по",
        "из",
        "от",
        "до",
        "при",
        "с",
        "со",
        "к",
        "у",
        "о",
        "об",
        "и",
        "или",
        "а",

        "для",
        "что",
        "чего",
        "как",
        "где",
        "когда",
        "зачем",
        "почему",

        "какой",
        "какая",
        "какое",
        "какие",

        "можно",
        "ли",
        "нужно",
        "надо",
        "нужен",
        "нужна",
        "нужны",

        "используется",
        "используются",

        "это",
        "такое",
        "такая",
        "такие",

        "setretail",
        "setretail10",
    }

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[VectorSearchResultSchema]:

        distance = (
            self.model.embedding
            .cosine_distance(query_embedding)
            .label("distance")
        )

        query = (
            select(
                self.model,
                distance,
                DocumentORM.title,
                DocumentORM.source_url,
            )
            .join(
                DocumentORM,
                self.model.document_id
                == DocumentORM.id,
            )
            .where(self.model.is_active.is_(True))
            .order_by(distance)
            .limit(top_k)
        )

        result_query = (
            await self.session.execute(query)
        ).all()

        result_list = [
            VectorSearchResultSchema(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity=1 - distance_value,
                document_title=document_title,
                document_url=document_url,
            )
            for (
                chunk,
                distance_value,
                document_title,
                document_url,
            )
            in result_query
        ]

        return result_list

    # ================================================================
    # LEXICAL SEARCH
    #
    # Нужен для точных терминов:
    # "товарные полки"
    # "ОПЛАТЫ"
    # PLU
    # названия параметров
    # ================================================================

    def _extract_lexical_terms(
        self,
        query_text: str,
    ) -> list[str]:

        words = re.findall(
            r"[0-9a-zа-яё_][0-9a-zа-яё_.-]*",
            query_text.lower(),
        )

        terms = []

        for word in words:

            if len(word) < 2:
                continue

            if word in self.LEXICAL_STOP_WORDS:
                continue

            if word in terms:
                continue

            terms.append(word)

        return terms[:10]

    async def search_lexical(
        self,
        query_text: str,
        top_k: int = 20,
    ) -> list[VectorSearchResultSchema]:

        terms = self._extract_lexical_terms(
            query_text
        )

        if not terms:
            return []

        title_text = func.lower(
            func.coalesce(
                DocumentORM.title,
                "",
            )
        )

        content_text = func.lower(
            func.coalesce(
                self.model.content,
                "",
            )
        )

        conditions = []

        score_expression = literal(0.0)

        # ------------------------------------------------------------
        # Каждый найденный термин даёт баллы.
        #
        # Совпадение в title весит больше.
        # ------------------------------------------------------------

        for term in terms:

            title_match = title_text.contains(
                term
            )

            content_match = content_text.contains(
                term
            )

            conditions.extend([
                title_match,
                content_match,
            ])

            score_expression = (
                score_expression
                + case(
                    (title_match, 2.0),
                    else_=0.0,
                )
                + case(
                    (content_match, 1.0),
                    else_=0.0,
                )
            )

        # ------------------------------------------------------------
        # Дополнительный boost за точную фразу.
        #
        # Для:
        #
        # "Для чего используются товарные полки?"
        #
        # после очистки получим:
        #
        # "товарные полки"
        # ------------------------------------------------------------

        phrase = " ".join(terms)

        phrase_bonus = 0.0

        if len(terms) >= 2:

            title_phrase_match = (
                title_text.contains(phrase)
            )

            content_phrase_match = (
                content_text.contains(phrase)
            )

            conditions.extend([
                title_phrase_match,
                content_phrase_match,
            ])

            score_expression = (
                score_expression
                + case(
                    (title_phrase_match, 6.0),
                    else_=0.0,
                )
                + case(
                    (content_phrase_match, 4.0),
                    else_=0.0,
                )
            )

            phrase_bonus = 10.0

        for negative_phrase in list(dict.fromkeys(re.findall(
            r"\bне\s+[а-яёa-z][а-яёa-z-]{2,}\b", query_text.lower(),
        )))[:5]:
            negative_match = content_text.contains(negative_phrase)
            conditions.append(negative_match)
            score_expression += case((negative_match, 4.0), else_=0.0)
            phrase_bonus += 4.0

        lexical_score = (
            score_expression.label(
                "lexical_score"
            )
        )

        query = (
            select(
                self.model,
                lexical_score,
                DocumentORM.title,
                DocumentORM.source_url,
            )
            .join(
                DocumentORM,
                self.model.document_id
                == DocumentORM.id,
            )
            .where(self.model.is_active.is_(True))
            .where(
                or_(*conditions)
            )
            .order_by(
                lexical_score.desc(),
                self.model.chunk_index,
            )
            .limit(top_k)
        )

        result_query = (
            await self.session.execute(query)
        ).all()

        max_score = (
            len(terms) * 3.0
            + phrase_bonus
        )

        result_list = [
            VectorSearchResultSchema(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity=min(
                    1.0,
                    float(score) / max_score,
                ),
                document_title=document_title,
                document_url=document_url,
            )
            for (
                chunk,
                score,
                document_title,
                document_url,
            )
            in result_query
        ]

        return result_list

    async def get_neigbors(
        self,
        document_id: UUID,
        chunk_index: int,
        radius: int = 1,
    ) -> list[DocumentChunkSchema]:

        indexes = list(
            range(
                max(
                    0,
                    chunk_index - radius,
                ),
                chunk_index + radius + 1,
            )
        )

        query = (
            select(self.model)
            .filter_by(
                document_id=document_id, is_active=True
            )
            .filter(
                self.model.chunk_index.in_(
                    indexes
                )
            )
            .order_by(
                self.model.chunk_index
            )
        )

        result_query = (
            await self.session.execute(query)
        ).scalars().all()

        return [
            self.mapper.map_to_domain_entity(
                obj
            )
            for obj in result_query
        ]

    async def get_neighbors_bulk(
        self,
        positions: list[tuple[UUID, int]],
        radius: int = 1,
    ) -> dict[tuple[UUID, int], list[DocumentChunkSchema]]:
        if not positions:
            return {}
        indexes_by_document = {}
        for document_id, index in positions:
            indexes_by_document.setdefault(document_id, set()).update(
                range(max(0, index - radius), index + radius + 1)
            )
        query = select(self.model).where(self.model.is_active.is_(True)).where(or_(*[
            (self.model.document_id == document_id)
            & self.model.chunk_index.in_(indexes)
            for document_id, indexes in indexes_by_document.items()
        ]))
        rows = (await self.session.execute(query)).scalars().all()
        chunks = {
            (row.document_id, row.chunk_index): self.mapper.map_to_domain_entity(row)
            for row in rows
        }
        return {
            (document_id, index): [
                chunks[(document_id, neighbor)]
                for neighbor in range(max(0, index - radius), index + radius + 1)
                if (document_id, neighbor) in chunks
            ]
            for document_id, index in positions
        }

    async def search_headings(self, pattern: str, top_k: int = 10) -> list[VectorSearchResultSchema]:
        query = (
            select(self.model, DocumentORM.title, DocumentORM.source_url)
            .join(DocumentORM, self.model.document_id == DocumentORM.id)
            .where(self.model.is_active.is_(True), self.model.content.op("~")(pattern))
            .order_by(self.model.document_id, self.model.chunk_index)
            .limit(top_k)
        )
        rows = (await self.session.execute(query)).all()
        return [
            VectorSearchResultSchema(
                chunk_id=chunk.id, document_id=chunk.document_id,
                chunk_index=chunk.chunk_index, content=chunk.content,
                similarity=0.0, document_title=title, document_url=url,
            )
            for chunk, title, url in rows
        ]

    async def get_by_document_id(
        self,
        document_id: UUID,
    ) -> list[DocumentChunkSchema]:

        query = (
            select(self.model)
            .filter_by(
                document_id=document_id, is_active=True
            )
            .order_by(
                self.model.chunk_index
            )
        )

        result_query = (
            await self.session.execute(query)
        ).scalars().all()

        return [
            self.mapper.map_to_domain_entity(
                obj
            )
            for obj in result_query
        ]

    async def retire_by_document_id(
        self,
        document_id: UUID,
    ) -> None:

        await self.session.execute(
            update(self.model).where(self.model.document_id == document_id).values(is_active=False)
        )
        query = (
            delete(self.model)
            .where(
                self.model.document_id
                == document_id,
                self.model.id.not_in(select(MessageSourceORM.chunk_id)),
            )
        )

        await self.session.execute(query)
