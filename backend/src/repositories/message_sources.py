from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import MessageSourceMapper
from src.models.message_sources import MessageSourceORM


class MessageSourceRepository(BaseRepository):
    model = MessageSourceORM
    mapper = MessageSourceMapper



