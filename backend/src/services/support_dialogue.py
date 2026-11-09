from copy import deepcopy

from fastapi import HTTPException

from src.config import settings
from src.schemas.support import SupportReply
from src.services.base import BaseService
from src.services.diagnosis import is_ready, ticket_details
from src.services.support_agent import respond
from src.services.vector_search import VectorSearchService
from src.services.rag import RAGService
from src.services.receipt_choices import choices_for
from src.services.receipt_instructions import select_instruction, PAPER_SECTIONS

WELCOME = (
    "Опишите неисправность и текст ошибки. Не отправляйте пароли и персональные данные."
)


class SupportDialogueService(BaseService):
    async def role(self, user_id, staff=False):
        role = await self.db.support.role(user_id)
        if role is None:
            raise HTTPException(401, "Учётная запись недоступна")
        if staff and role not in {"admin", "it"}:
            raise HTTPException(403, "Требуются права поддержки")
        return role

    async def create(self, user_id):
        await self.role(user_id)
        row = await self.db.support.create_session(user_id)
        await self.db.commit()
        return {**row, "answer": WELCOME, "choices": choices_for(row["state"])}

    async def get(self, session_id, user_id, lock=False):
        await self.role(user_id)
        row = await self.db.support.get_session(session_id, user_id, lock=lock)
        if row is None:
            raise HTTPException(404, "Диалог не найден")
        return {**row, "choices": choices_for(row["state"])}

    def replay(self, history, data):
        for entry in history:
            if (
                entry.get("request_id") == str(data.request_id)
                and entry.get("role") == "assistant"
            ):
                if entry.get("question") != data.message or entry.get("choice_id") != data.choice_id:
                    raise HTTPException(
                        409,
                        "Идентификатор запроса уже использован для другого сообщения",
                    )
                return SupportReply.model_validate(entry["response"])
        return None

    async def send(self, session_id, user_id, data, models):
        row = await self.get(session_id, user_id)
        replay = self.replay(row["history"], data)
        if replay:
            return replay
        if row["ticket_id"]:
            return SupportReply(
                answer="Заявка уже зарегистрирована. Её статус доступен в разделе «Мои заявки».",
                ticket_id=row["ticket_id"],
                request_id=data.request_id,
                version=row["version"],
                phase="ticket_created",
                engine="system",
            )
        if len(row["history"]) >= 120:
            raise HTTPException(409, "Диалог достиг лимита. Начните новое обращение.")
        await self.db.commit()
        state = deepcopy(row["state"])
        message = data.message
        if data.choice_id:
            choice = next((item for item in choices_for(state) if item["id"] == data.choice_id), None)
            if choice is None:
                raise HTTPException(409, "Вопрос изменился. Обновите диалог и выберите ответ снова.")
            message = choice["label"]
        normalized = message.casefold().rstrip(".!?")
        create_ticket = is_ready(state) and normalized in {"да", "yes", "отправить"}
        if create_ticket:
            answer = ""
        else:

            async def retrieve(query):
                chunks = await VectorSearchService(self.db, models["embedding"]).search(
                    query, top_k=4
                )
                return [
                    {
                        "title": chunk.document_title,
                        "url": chunk.document_url,
                        "content": chunk.content[:2500],
                    }
                    for chunk in chunks
                ]

            async def lookup(query, flow):
                if flow.get("paper_missing"):
                    prefix = PAPER_SECTIONS.get(flow["model"])
                    sections = await self.db.documents.find_instruction_sections(prefix) if prefix else []
                    documents = [({"title": doc.title, "url": doc.source_url}, doc.content) for doc in sections]
                    return select_instruction({}, documents, flow)
                if models.get("status") != "ready":
                    return {"status": "loading", "sources": []}
                rag = RAGService(self.db, VectorSearchService(self.db, models["embedding"]),
                                 models["llm"], models["reranker"])
                result = await rag.answer(query)
                payload = result.model_dump(mode="json")
                documents = []
                for source in payload["sources"]:
                    document = await self.db.documents.find_url(source["url"])
                    if document and not document.is_archived:
                        documents.append((source, document.content))
                return select_instruction(payload, documents, flow)

            try:
                state, answer = await respond(
                    state,
                    row["history"],
                    message,
                    models.get("llm") if models.get("status") == "ready" else None,
                    retrieve,
                    timeout=settings.SUPPORT_MODEL_TIMEOUT_SECONDS,
                    lookup=lookup,
                )
            finally:
                await self.db.rollback()
        current = await self.get(session_id, user_id, lock=True)
        replay = self.replay(current["history"], data)
        if replay:
            return replay
        if current["version"] != row["version"]:
            raise HTTPException(
                409,
                "В диалоге появилось новое сообщение. Обновите историю и повторите отправку.",
            )
        ticket_id = current["ticket_id"]
        if create_ticket:
            details = ticket_details(state)
            details["transcript"] = [
                {"role": entry["role"], "content": entry["content"]}
                for entry in current["history"]
            ]
            ticket = await self.db.support.create_ticket(session_id, user_id, details)
            ticket_id = ticket["id"]
            await self.db.support.add_event(
                ticket_id, user_id, {"event": "created", "status": "open"}
            )
            state["_phase"] = "ticket_created"
            answer = f"Заявка {ticket_id} зарегистрирована. Статус и решение будут доступны в разделе «Мои заявки»."
        reply = SupportReply(
            answer=answer,
            choices=choices_for(state),
            ticket_id=ticket_id,
            request_id=data.request_id,
            version=current["version"] + 1,
            phase=state.get("_phase", "collect"),
            engine="system" if create_ticket else state.get("_engine", "rules"),
        )
        history = current["history"] + [
            {
                "role": "user",
                "content": message,
                "request_id": str(data.request_id),
            },
            {
                "role": "assistant",
                "content": answer,
                "request_id": str(data.request_id),
                "question": data.message,
                "choice_id": data.choice_id,
                "response": reply.model_dump(mode="json"),
            },
        ]
        await self.db.support.save_session(session_id, state, history, ticket_id)
        await self.db.commit()
        return reply

    async def list_tickets(self, user_id, queue, status, offset, limit):
        await self.role(user_id, staff=queue)
        return await self.db.support.list_tickets(
            None if queue else user_id, status, offset, limit
        )

    async def ticket(self, ticket_id, user_id):
        role = await self.role(user_id)
        ticket = await self.db.support.get_ticket(ticket_id)
        if not ticket or (ticket["user_id"] != user_id and role not in {"admin", "it"}):
            raise HTTPException(404, "Заявка не найдена")
        return {
            **ticket,
            "history": await self.db.support.ticket_history(ticket["session_id"]),
            "events": await self.db.support.events(ticket_id),
        }

    async def update_ticket(self, ticket_id, user_id, data):
        await self.role(user_id, staff=True)
        ticket = await self.db.support.get_ticket(ticket_id, lock=True)
        if ticket is None:
            raise HTTPException(404, "Заявка не найдена")
        if ticket["version"] != data.version:
            raise HTTPException(
                409,
                "Заявка изменена другим специалистом. Обновите её перед сохранением.",
            )
        if data.status == "resolved" and not data.resolution:
            raise HTTPException(422, "Укажите решение")
        assigned_to = user_id if data.assign_to_me else ticket["assigned_to"]
        updated = await self.db.support.update_ticket(
            ticket_id, data.status, data.resolution, assigned_to
        )
        await self.db.support.add_event(
            ticket_id,
            user_id,
            {
                "event": "updated",
                "previous_status": ticket["status"],
                "status": data.status,
                "resolution": data.resolution,
                "comment": data.comment,
                "assigned_to": assigned_to,
            },
        )
        await self.db.commit()
        return updated
