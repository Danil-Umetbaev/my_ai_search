import logging

from src.schemas.chat import ChatRequest, ChatResponse, SourceResponse, ChatStatus
from src.services.rag import RAGService
from src.utils.db import DBManager
from src.services.base import BaseService
from src.schemas.messages import MessageAddSchema, MessageSourceAddSchema
from src.exceptions import NoResultFoundException, NoConversationFoundException, RAGProcessingException
from src.models.enums import Role, Status
from src.schemas.rag import RAGStatus
from src.services.escalation import EscalationService

logger = logging.getLogger(__name__)


class ChatService(BaseService):
    def __init__(self, db: DBManager, rag_service: RAGService, escalation_service: EscalationService):
        super().__init__(db)
        self.rag_service = rag_service
        self.escalation_service = escalation_service

    async def send_message(self, data: ChatRequest) -> ChatResponse:
        try:
            await self.db.conversations.get_one(id=data.conversation_id)
        except NoResultFoundException:
            raise NoConversationFoundException

        await self.db.messages.add(MessageAddSchema(
            conversation_id=data.conversation_id, content=data.message, role=Role.user,
        ))
        try:
            result = await self.rag_service.answer(data.message)
        except Exception as ex:
            logger.exception("RAG processing failed | conversation_id=%s", data.conversation_id)
            raise RAGProcessingException from ex

        status = ChatStatus(result.status.value)
        sources = []
        content = result.answer
        if result.status == RAGStatus.NOT_FOUND:
            content = "В документации SetRetail10 не найден ответ на этот вопрос. Попробуйте уточнить формулировку."
            if self.escalation_service.enabled:
                escalation = await self.escalation_service.escalate(
                    conversation_id=data.conversation_id,
                    question=data.message,
                    reason="Не найден ответ, подтверждённый документацией.",
                )
                content = (
                    "Информация не найдена. Вопрос передан специалистам."
                    if escalation.status == Status.sent else
                    "Информация не найдена. Не удалось отправить уведомление специалистам. Обратитесь в поддержку."
                )
        elif result.status == RAGStatus.ANSWERED:
            sources = [SourceResponse(title=s.title, url=s.url, score=s.score) for s in result.sources]

        response = ChatResponse(
            status=status,
            answer=content if status != ChatStatus.NOT_FOUND else None,
            message=content if status == ChatStatus.NOT_FOUND else None,
            sources=sources,
            confidence=result.confidence,
        )
        saved = await self.db.messages.add(MessageAddSchema(
            conversation_id=data.conversation_id,
            content=content,
            role=Role.assistant,
            response_meta={
                "status": status.value,
                "sources": [s.model_dump(mode="json") for s in sources],
                "confidence": result.confidence,
            },
        ))
        if status == ChatStatus.ANSWERED and result.used_chunks:
            await self.db.message_sources.add_bulk([
                MessageSourceAddSchema(message_id=saved.id, chunk_id=c.chunk_id, relevance_score=c.score)
                for c in result.used_chunks
            ])
        await self.db.commit()
        response.message_id = saved.id
        return response
