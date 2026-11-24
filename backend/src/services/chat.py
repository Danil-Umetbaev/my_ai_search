import logging
from src.services.conversation import ConversationService
from src.services import conversation_diagnosis

from src.schemas.chat import ChatRequest, ChatResponse, SourceResponse, ChatStatus
from src.services.rag import RAGService
from src.utils.db import DBManager
from src.services.base import BaseService
from src.schemas.messages import MessageAddSchema, MessageSourceAddSchema
from src.exceptions import (
    ChatRequestConflictException,
    AIServiceUnavailableException,
    RAGProcessingException,
)
from src.models.enums import Role, Status
from src.schemas.rag import RAGStatus
from src.services.escalation import EscalationService

logger = logging.getLogger(__name__)


class ChatService(BaseService):
    def __init__(
        self,
        db: DBManager,
        rag_service: RAGService,
        escalation_service: EscalationService,
    ):
        super().__init__(db)
        self.rag_service = rag_service
        self.escalation_service = escalation_service

    async def send_message(self, data: ChatRequest, user=None) -> ChatResponse:
        stored = await ConversationService(self.db).accessible_state(
            data.conversation_id, user, for_update=True
        )
        if user is not None and stored.get("_chat_owner") is None:
            stored["_chat_owner"] = user.id
            await self.db.conversations.save_state(data.conversation_id, stored)
        history = await self.db.messages.get_messages_by_conversation_id(data.conversation_id)
        for entry in history:
            meta = entry.response_meta
            if meta.get("request_id") == str(data.request_id):
                if meta.get("question") != data.message or meta.get("choice_id") != data.choice_id:
                    raise ChatRequestConflictException
                return ChatResponse.model_validate({**meta["reply"], "message_id": entry.id})
        state = stored.get("diagnosis", {})
        active = state and state.get("_phase") not in {"resolved", "cancelled", "ticket_created"}
        if active or data.choice_id or conversation_diagnosis.is_problem(data.message):
            async def escalate():
                return await self.escalation_service.escalate(
                    data.conversation_id, state.get("problem", data.message),
                    "Диагностика завершена. Переписка сохранена в диалоге.",
                )
            transcript = [{"role": entry.role.value, "content": entry.content} for entry in history]
            state, answer = await conversation_diagnosis.respond(
                self.db, state, data.message, data.choice_id, transcript, user,
                getattr(self.rag_service, "llm", None), escalate,
            )
            reply = ChatResponse(
                status=ChatStatus.ANSWERED, answer=answer, confidence=None,
                choices=conversation_diagnosis.options(state), phase=state["_phase"],
            )
            await self.db.messages.add(MessageAddSchema(
                conversation_id=data.conversation_id, role=Role.user, content=data.message,
            ))
            meta = {
                **reply.model_dump(mode="json"), "question": data.message,
                "request_id": str(data.request_id), "choice_id": data.choice_id,
                "reply": reply.model_dump(mode="json"),
            }
            saved = await self.db.messages.add(MessageAddSchema(
                conversation_id=data.conversation_id, role=Role.assistant,
                content=answer, response_meta=meta,
            ))
            stored["diagnosis"] = state
            await self.db.conversations.save_state(data.conversation_id, stored)
            await self.db.commit()
            reply.message_id = saved.id
            return reply

        if self.rag_service is None:
            raise AIServiceUnavailableException

        await self.db.messages.add(
            MessageAddSchema(
                conversation_id=data.conversation_id,
                content=data.message,
                role=Role.user,
            )
        )
        try:
            result = await self.rag_service.answer(data.message)
        except Exception as ex:
            logger.exception(
                "RAG processing failed | conversation_id=%s", data.conversation_id
            )
            raise RAGProcessingException from ex

        status = ChatStatus(result.status.value)
        sources = []
        content = result.answer
        if result.status == RAGStatus.NOT_FOUND:
            escalation = await self.escalation_service.escalate(
                conversation_id=data.conversation_id,
                question=data.message,
                reason="Не найден ответ, подтверждённый документацией.",
            )
            content = (
                "В документации не найден ответ. Обращение сохранено для специалиста."
            )
            if escalation.status == Status.sent:
                content += " Уведомление отправлено."
            elif escalation.status == Status.failed:
                content += " Уведомление доставить не удалось."
        elif result.status == RAGStatus.ANSWERED:
            sources = [
                SourceResponse(title=s.title, url=s.url, score=s.score)
                for s in result.sources
            ]

        response = ChatResponse(
            status=status,
            answer=content if status != ChatStatus.NOT_FOUND else None,
            message=content if status == ChatStatus.NOT_FOUND else None,
            sources=sources,
            confidence=result.confidence,
        )
        saved = await self.db.messages.add(
            MessageAddSchema(
                conversation_id=data.conversation_id,
                content=content,
                role=Role.assistant,
                response_meta={
                    "request_id": str(data.request_id),
                    "choice_id": data.choice_id,
                    "reply": response.model_dump(mode="json"),
                    "status": status.value,
                    "question": data.message,
                    "sources": [s.model_dump(mode="json") for s in sources],
                    "confidence": result.confidence,
                },
            )
        )
        if status == ChatStatus.ANSWERED and result.used_chunks:
            await self.db.message_sources.add_bulk(
                [
                    MessageSourceAddSchema(
                        message_id=saved.id,
                        chunk_id=c.chunk_id,
                        relevance_score=c.score,
                    )
                    for c in result.used_chunks
                ]
            )
        await self.db.commit()
        response.message_id = saved.id
        return response
