from uuid import UUID

from sqlalchemy import select

from src.models.messages import MessageORM
from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import  MessageDataMapper

class MessageRepository(BaseRepository):
    mapper = MessageDataMapper
    model = MessageORM


    async def get_messages_by_conversation_id(self, conversation_id: UUID):
        query = (select(self.model)).filter_by(conversation_id=conversation_id).order_by(self.model.created_at)
        result = await self.session.execute(query)
        objects = result.scalars().all()
        return [self.mapper.map_to_domain_entity(obj) for obj in objects]