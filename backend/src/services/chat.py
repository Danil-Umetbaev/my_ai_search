import logging

from src.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceResponse,
    ChatStatus,
)
from src.services.rag import RAGService
from src.utils.db import DBManager
from src.services.base import BaseService
from src.schemas.messages import (
    MessageAddSchema,
    MessageSourceAddSchema,
)
from src.exceptions import (
    NoResultFoundException,
    NoConversationFoundException,
    RAGProcessingException,
)
from src.models.enums import Role
from src.schemas.rag import RAGStatus
from src.services.escalation import EscalationService


logger = logging.getLogger(__name__)

class ChatService(BaseService):

    def __init__(self, db: DBManager, rag_service: RAGService, escalation_service: EscalationService):
        super().__init__(db)
        self.rag_service = rag_service
        self.escalation_service = escalation_service

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

        try:
            rag_result = await self.rag_service.answer(message_schema.content)
        except Exception as ex:
            logger.exception(
                "RAG processing failed | conversation_id=%s",
                data.conversation_id
            )
            raise RAGProcessingException from ex
        if rag_result.status == RAGStatus.OFF_TOPIC:
            assistant_message = MessageAddSchema(
                conversation_id=data.conversation_id,
                content=rag_result.answer,
                role=Role.assistant
            )

            saved_assistant_message = await self.db.messages.add(
                assistant_message
            )

            await self.db.commit()

            return ChatResponse(
                message_id=saved_assistant_message.id,
                status=ChatStatus.OFF_TOPIC,
                answer=rag_result.answer,
                message=None,
                sources=[],
                confidence=None
            )
        if rag_result.status == RAGStatus.NOT_FOUND:
            if not self.escalation_service.enabled:
                message = await self.db.messages.add(MessageAddSchema(
                    conversation_id=data.conversation_id,
                    content="В документации SetRetail10 не найден ответ на этот вопрос. Попробуйте уточнить формулировку.",
                    role=Role.assistant,
                ))
                await self.db.commit()
                return ChatResponse(
                    message_id=message.id, status=ChatStatus.NOT_FOUND,
                    answer=None, message=message.content, sources=[],
                    confidence=rag_result.confidence,
                )
            await self.escalation_service.escalate(
                conversation_id=data.conversation_id,
                question=data.message,
                reason="Недостаточная релевантность документов."
            )
            assistant_message = MessageAddSchema(
                conversation_id=data.conversation_id, content="Информация не найдена. Вопрос передан специалистам.", role=Role.assistant
            )
            saved_assistant_message = await self.db.messages.add(assistant_message)
            await self.db.commit()
            return ChatResponse(
                message_id=saved_assistant_message.id,
                status=ChatStatus.ESCALATED,
                answer=None,
                message=saved_assistant_message.content,
                sources=[],
                confidence=rag_result.confidence
            )
        assistant_message = MessageAddSchema(conversation_id=data.conversation_id, content=rag_result.answer, role=Role.assistant)
        saved_assistant_message = await self.db.messages.add(assistant_message)
        message_sources = [MessageSourceAddSchema(message_id=saved_assistant_message.id, chunk_id=chunk.chunk_id, relevance_score=chunk.score) for chunk in rag_result.used_chunks]

        if message_sources:
            await self.db.message_sources.add_bulk(message_sources)
        sources = [SourceResponse(title=source.title, url=source.url, score=source.score) for source in rag_result.sources]
        await self.db.commit()


        return ChatResponse(
            message_id=saved_assistant_message.id,
            status=ChatStatus.ANSWERED,
            answer=rag_result.answer,
            sources=sources,
            message=None,
            confidence=rag_result.confidence
        )


