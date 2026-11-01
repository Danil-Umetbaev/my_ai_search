from src.repositories.base import BaseRepository
from src.models.conversations import ConversationORM
from src.repositories.mappers.mappers import ConversationDataMapper


class ConversationsRepository(BaseRepository):
    mapper = ConversationDataMapper
    model = ConversationORM

    async def delete_with_related(self, object_id):
        from sqlalchemy import delete, select
        from src.models.messages import MessageORM
        from src.models.message_sources import MessageSourceORM
        from src.models.escalations import EscalationORM

        await self.get_one(id=object_id, for_update=True)
        message_ids = select(MessageORM.id).where(
            MessageORM.conversation_id == object_id
        )
        await self._execute(
            delete(MessageSourceORM).where(MessageSourceORM.message_id.in_(message_ids))
        )
        await self._execute(
            delete(EscalationORM).where(EscalationORM.conversation_id == object_id)
        )
        await self._execute(
            delete(MessageORM).where(MessageORM.conversation_id == object_id)
        )
        await super().delete(id=object_id)
