import logging

from src.schemas.chat import ChatRequest, ChatResponse, SourceResponse, ChatStatus
from src.services.rag import RAGService
from src.services.dialogue import DialogueService
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
        self.dialogue = DialogueService()

    async def _reply(self, conversation_id, state, status, answer, sources=None, chunks=None, confidence=None, choices=None):
        sources = sources or []
        choices = choices or []
        meta = {"status": status.value, "choices": choices, "sources": [source.model_dump(mode="json") for source in sources], "confidence": confidence}
        message = await self.db.messages.add(MessageAddSchema(
            conversation_id=conversation_id, content=answer, role=Role.assistant, response_meta=meta,
        ))
        if chunks:
            await self.db.message_sources.add_bulk([MessageSourceAddSchema(
                message_id=message.id, chunk_id=chunk.chunk_id, relevance_score=chunk.score,
            ) for chunk in chunks])
        await self.db.conversations.save_support_state(conversation_id, state)
        await self.db.commit()
        return ChatResponse(message_id=message.id, status=status, answer=answer, message=None,
                            sources=sources, confidence=confidence, choices=choices)

    async def _handoff(self, conversation_id, state, reason):
        summary = self.dialogue.summary(state)
        state["stage"] = "handoff"
        state["pending"] = None
        await self.db.conversations.save_support_state(conversation_id, state)
        if not self.escalation_service.enabled:
            return await self._reply(conversation_id, state, ChatStatus.NOT_FOUND,
                "Нужна помощь специалиста. Автоматическая отправка в поддержку не настроена. Передайте ей эту информацию:\n\n" + summary)
        escalation = await self.escalation_service.escalate(conversation_id=conversation_id, question=summary, reason=reason)
        sent = escalation.status == Status.sent
        answer = ("Передал обращение специалистам вместе с собранной информацией." if sent else
                  "Не удалось отправить уведомление специалистам. Обратитесь в поддержку и передайте эту информацию:")
        return await self._reply(conversation_id, state, ChatStatus.ESCALATED if sent else ChatStatus.NOT_FOUND,
                                 answer + "\n\n" + summary)

    async def send_message(self, data: ChatRequest) -> ChatResponse:
        try:
            state = await self.db.conversations.lock_support_state(data.conversation_id)
        except NoResultFoundException:
            raise NoConversationFoundException
        await self.db.messages.add(MessageAddSchema(conversation_id=data.conversation_id, content=data.message, role=Role.user))
        decision = self.dialogue.route(data.message, state)
        if decision.action == "interpret":
            decision = await self.dialogue.interpret(data.message, decision.state, self.rag_service.llm)
        state = decision.state
        if decision.action == "clarify":
            return await self._reply(data.conversation_id, state, ChatStatus.CLARIFICATION, decision.answer, choices=decision.choices)
        if decision.action == "off_topic":
            return await self._reply(data.conversation_id, state, ChatStatus.OFF_TOPIC, decision.answer, choices=decision.choices)
        if decision.action == "resolved":
            return await self._reply(data.conversation_id, state, ChatStatus.RESOLVED, decision.answer)
        if decision.action == "handoff":
            return await self._handoff(data.conversation_id, state, "Запрошена помощь специалиста или исчерпаны уточнения.")
        incident = decision.action == "search" and state.get("mode") != "question"
        try:
            rag_result = await self.rag_service.answer(decision.query, support_mode=incident)
        except Exception as ex:
            logger.exception("RAG processing failed | conversation_id=%s", data.conversation_id)
            raise RAGProcessingException from ex
        if rag_result.status == RAGStatus.CLARIFICATION:
            followup = self.dialogue.ask_from_evidence(state, rag_result.answer, data.message)
            if followup.action == "handoff":
                return await self._handoff(data.conversation_id, followup.state, "Не удалось выбрать инструкцию после уточнений.")
            return await self._reply(data.conversation_id, followup.state, ChatStatus.CLARIFICATION, followup.answer)
        if rag_result.status == RAGStatus.OFF_TOPIC:
            return await self._reply(data.conversation_id, state, ChatStatus.OFF_TOPIC, rag_result.answer)
        if rag_result.status == RAGStatus.NOT_FOUND:
            if incident:
                followup = self.dialogue.missing_answer(state)
                if followup.action == "clarify":
                    return await self._reply(data.conversation_id, followup.state, ChatStatus.CLARIFICATION,
                                             followup.answer, choices=followup.choices)
            if not state:
                state = {"initial": data.message, "facts": {}}
            return await self._handoff(data.conversation_id, state, "Не найдена подтверждённая инструкция для сотрудника.")
        sources = [SourceResponse(title=source.title, url=source.url, score=source.score) for source in rag_result.sources]
        choices = []
        answer = rag_result.answer
        if state.get("mode") == "question":
            state = {}
        if incident:
            state["stage"] = "awaiting_result"
            state["searches"] = state.get("searches", 0) + 1
            state["last_answer"] = answer[:1500]
            answer += "\n\nЭто помогло решить проблему?"
            choices = ["Помогло", "Не помогло", "Позовите специалиста"]
        return await self._reply(data.conversation_id, state, ChatStatus.ANSWERED, answer,
                                 sources, rag_result.used_chunks, rag_result.confidence, choices)
