from src.schemas.chat import ChatRequest, ChatResponse, SourceResponse
from src.services.rag import RAGService
from src.utils.db import DBManager
from src.services.base import BaseService
from src.schemas.messages import MessageAddSchema
from src.exceptions import NoResultFoundException, NoConversationFoundException
from src.models.enums import Role
from src.schemas.rag import RAGStatus
class ChatService(BaseService):

    def __init__(self, db: DBManager, rag_service: RAGService):
        super().__init__(db)
        self.rag_service = rag_service

    async def send_message(
            self,
            data: ChatRequest
    ) -> ChatResponse:

        try:
            await self.db.conversations.get_one(id=data.conversation_id)
        except NoResultFoundException:
            raise NoConversationFoundException
        new_message = MessageAddSchema(conversation_id=data.conversation_id, content=data.message, role=Role.user)
        message_schema = await self.db.messages.add(new_message)
        rag_result = await self.rag_service.answer(message_schema.content)

        if rag_result.status == RAGStatus.NOT_FOUND:
            await self.db.commit()
            return ChatResponse(
                message_id=None,
                status=RAGStatus.NOT_FOUND,
                answer=None,
                sources=[],
                confidence=rag_result.confidence
            )
        assistant_message = MessageAddSchema(conversation_id=data.conversation_id, content=rag_result.answer, role=Role.assistant)
        saved_assistant_message = await self.db.messages.add(assistant_message)

        sources = [SourceResponse(title=source.title, url=source.url) for source in rag_result.sources]
        await self.db.commit()


        return ChatResponse(
            message_id=saved_assistant_message.id,
            status=RAGStatus.ANSWERED,
            answer=rag_result.answer,
            sources=sources,
            confidence=rag_result.confidence
        )


