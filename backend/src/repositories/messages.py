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

    async def get_admin_messages(self, conversation_id, limit=50, offset=0):
        from sqlalchemy import func

        condition = self.model.conversation_id == conversation_id
        total = (
            await self.execute_admin(
                select(func.count()).select_from(self.model).where(condition)
            )
        ).scalar_one()
        rows = (
            (
                await self.execute_admin(
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
