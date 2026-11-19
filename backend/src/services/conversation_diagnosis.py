"""Use the reviewed diagnostic tree inside the main conversation."""
import re
from copy import deepcopy

from fastapi import HTTPException

from src.services import atol_support_tree as tree, atol_semantic_router
from src.services.support_knowledge import SupportKnowledgeService
from src.services.diagnosis import ticket_details


def is_problem(message):
    text = message.casefold().replace("ё", "е")
    if text in {"диагностика", "нужен специалист", "передать специалисту"}:
        return True
    return bool(re.search(
        r"не\s*(?:печата|работа|включа|видит|реагиру|отправ|закрыва)|"
        r"зажев|замят|застрял|ошибк|заблокир|бледн|закончилась.*(?:бумага|лента)",
        text,
    ))


async def respond(db, state, message, choice_id, history, user, llm, escalation):
    state = deepcopy(state)
    if not state or state.get("_phase") in {"resolved", "cancelled", "ticket_created"}:
        if choice_id:
            raise HTTPException(409, "Вопрос изменился. Обновите диалог.")
        state = tree.initial_state()
        state["problem"] = message
        state["_opening_description"] = message

    if choice_id:
        choice = next((c for c in options(state) if c["id"] == choice_id), None)
        if not choice:
            raise HTTPException(409, "Вопрос изменился. Обновите диалог.")
        message = choice["label"]

    if state.get("_phase") == "confirm" and message in {"Отправить специалисту", "да", "отправить"}:
        details = ticket_details(state)
        transcript = history + [{"role": "user", "content": message}]
        details["transcript"] = transcript
        if user:
            session = await db.support.create_session(user.id)
            ticket = await db.support.create_ticket(session["id"], user.id, details)
            await db.support.add_event(ticket["id"], user.id, {"event": "created", "status": "open"})
            state["_phase"] = "ticket_created"
            await db.support.save_session(session["id"], state, transcript, ticket["id"])
            answer = f"Заявка {ticket['id']} зарегистрирована. Решение появится в разделе «Мои заявки»."
        else:
            await escalation()
            state["_phase"] = "ticket_created"
            answer = "Обращение и переписка сохранены для специалиста."
        return state, answer

    async def lookup(query, flow):
        return await SupportKnowledgeService(db).lookup(query, flow, user.role.value if user else "kassir")

    if message == "Диагностика":
        return state, tree.render(state)
    state, answer = await atol_semantic_router.advance(
        state, message, history, llm=llm, button=bool(choice_id), lookup=lookup
    )
    # Reuse the original symptom once the user confirms the model.
    opening = state.get("_opening_description")
    node = state["_atol_tree"]["node"]
    if opening and node in {"categories", "pirit_categories", "viki_categories"}:
        state.pop("_opening_description")
        if is_problem(opening) and opening != "Диагностика":
            state, answer = await atol_semantic_router.advance(
                state, opening, history, llm=llm, lookup=lookup
            )
    return state, answer


def options(state):
    if state.get("_phase") == "confirm":
        revision = state["_atol_tree"]["revision"]
        return [
            {"id": f"handoff:{revision}:send", "label": "Отправить специалисту"},
            {"id": f"handoff:{revision}:cancel", "label": "Отмена"},
        ]
    return tree.choices(state)

