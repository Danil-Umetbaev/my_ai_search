
from src.repositories.base import BaseRepository
from src.models.conversations import ConversationORM
from src.repositories.mappers.mappers import ConversationDataMapper


class ConversationsRepository(BaseRepository):
    mapper = ConversationDataMapper
    model = ConversationORM


    async def lock_support_state(self, conversation_id):
        from sqlalchemy import select
        from src.exceptions import NoResultFoundException
        result = await self.session.execute(select(self.model).where(self.model.id == conversation_id).with_for_update())
        row = result.scalar_one_or_none()
        if row is None:
            raise NoResultFoundException
        return dict(row.support_state or {})

    async def save_support_state(self, conversation_id, state):
        from sqlalchemy import update
        await self.session.execute(update(self.model).where(self.model.id == conversation_id).values(support_state=state))
