from sqlalchemy import select, update
from src.exceptions import NoResultFoundException
from src.repositories.base import BaseRepository
from src.models.conversations import ConversationORM
from src.repositories.mappers.mappers import ConversationDataMapper


class ConversationsRepository(BaseRepository):
    mapper = ConversationDataMapper
    model = ConversationORM

    async def get_page(self, limit=50, offset=0, **filter_by):
        return await super().get_page(
            limit,
            offset,
            order_by=(self.model.created_at.desc(), self.model.id),
            **filter_by
        )

    async def get_state(self, conversation_id, *, for_update=False):
        query = select(self.model.support_state).where(self.model.id == conversation_id)
        if for_update:
            query = query.with_for_update()
        state = (await self._execute(query)).scalar_one_or_none()
        if state is None:
            raise NoResultFoundException
        return dict(state)

    async def save_state(self, conversation_id, state):
        result = await self._execute(
            update(self.model).where(self.model.id == conversation_id)
            .values(support_state=state)
        )
        if result.rowcount != 1:
            raise NoResultFoundException
