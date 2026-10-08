from src.repositories.conversations import ConversationsRepository
from src.repositories.messages import MessageRepository
from src.repositories.document_chunk import DocumentChunkRepository
from src.repositories.documents import DocumentRepository
from src.repositories.message_sources import MessageSourceRepository


class DBManager:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()

        self.conversations = ConversationsRepository(self.session)
        self.messages = MessageRepository(self.session)
        self.document_chunks = DocumentChunkRepository(self.session)
        self.documents = DocumentRepository(self.session)
        self.message_sources = MessageSourceRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()
        await self.session.close()

    async def commit(self):
        await self.session.commit()
