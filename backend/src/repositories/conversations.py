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
