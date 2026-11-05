
from src.repositories.base import BaseRepository
from src.models.conversations import ConversationORM
from src.repositories.mappers.mappers import ConversationDataMapper


class ConversationsRepository(BaseRepository):
    mapper = ConversationDataMapper
    model = ConversationORM

