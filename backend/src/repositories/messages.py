from uuid import UUID

from sqlalchemy import select

from src.models.messages import MessageORM
from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import MessageDataMapper


class MessageRepository(BaseRepository):
    mapper = MessageDataMapper
    model = MessageORM

    async def get_messages_by_conversation_id(self, conversation_id: UUID):
        query = (
            (select(self.model))
            .filter_by(conversation_id=conversation_id)
            .order_by(self.model.created_at)
        )
        result = await self.session.execute(query)
        objects = result.scalars().all()
        return [self.mapper.map_to_domain_entity(obj) for obj in objects]

    async def get_page_by_conversation_id(self, conversation_id, limit=50, offset=0):
        from sqlalchemy import func

        condition = self.model.conversation_id == conversation_id
        total = (
            await self._execute(
                select(func.count()).select_from(self.model).where(condition)
            )
        ).scalar_one()
        rows = (
            (
                await self._execute(
                    select(self.model)
                    .where(condition)
                    .order_by(self.model.created_at, self.model.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return {
            "items": [self.mapper.map_to_domain_entity(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_unanswered(self, limit=50, offset=0):
        from sqlalchemy import func
        from sqlalchemy.orm import aliased

        previous = aliased(self.model)
        prior_question = (
            select(previous.content)
            .where(
                previous.conversation_id == self.model.conversation_id,
                previous.role == "user",
                previous.created_at <= self.model.created_at,
            )
            .order_by(previous.created_at.desc(), previous.id.desc())
            .limit(1)
            .correlate(self.model)
            .scalar_subquery()
        )
        condition = (self.model.role == "assistant") & (
            self.model.response_meta["status"].astext == "not_found"
        )
        total = (
            await self._execute(
                select(func.count()).select_from(self.model).where(condition)
            )
        ).scalar_one()
        query = (
            select(
                self.model.id,
                self.model.conversation_id,
                self.model.created_at,
                func.coalesce(
                    self.model.response_meta["question"].astext,
                    prior_question,
                    "Вопрос в истории диалога",
                ).label("question"),
                self.model.content.label("answer"),
            )
            .where(condition)
            .order_by(self.model.created_at.desc(), self.model.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._execute(query)).mappings().all()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
