from src.models.messages import MessageORM
from src.schemas.messages import MessageSchema
from src.models.conversations import ConversationORM
from src.schemas.conversations import ConversationSchema
from src.repositories.mappers.base import DataMapper


class ConversationDataMapper(DataMapper):
    db_model = ConversationORM
    schema = ConversationSchema

class MessageDataMapper(DataMapper):
    db_model = MessageORM
    schema = MessageSchema