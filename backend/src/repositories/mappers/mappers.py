from src.models.messages import MessageORM
from src.schemas.messages import MessageSchema
from src.models.conversations import ConversationORM
from src.schemas.conversations import ConversationSchema
from src.repositories.mappers.base import DataMapper
from src.models.document_chunk import DocumentChunkORM
from src.schemas.document_chunks import DocumentChunkSchema
from src.models.documents import DocumentORM
from src.schemas.documents import DocumentSchema
from src.schemas.messages import MessageSourceSchema
from src.models.message_sources import MessageSourceORM
from src.models.escalations import EscalationORM
from src.schemas.escalations import EscalationSchema
from src.models.users import UsersORM
from src.schemas.users import User

class ConversationDataMapper(DataMapper):
    db_model = ConversationORM
    schema = ConversationSchema

class MessageDataMapper(DataMapper):
    db_model = MessageORM
    schema = MessageSchema


class DocumentDataMapper(DataMapper):
    db_model = DocumentORM
    schema = DocumentSchema

class DocumentChunkMapper(DataMapper):
    db_model = DocumentChunkORM
    schema = DocumentChunkSchema


class MessageSourceMapper(DataMapper):
    db_model = MessageSourceORM
    schema = MessageSourceSchema


class EscalationDataMapper(DataMapper):
    db_model = EscalationORM
    schema = EscalationSchema


class UserDataMapper(DataMapper):
    db_model = UsersORM
    schema = User
