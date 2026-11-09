"""Bounded receipt triage; repair instructions come only from the knowledge base."""

import asyncio
import logging
import re
from copy import deepcopy

from src.services.receipt_facts import (
    ALIASES,
    SELECTION_FACTS,
    check_result,
    collect_facts,
    model_candidates,
    normalize,
)

logger = logging.getLogger(__name__)
QUESTIONS = {
    "layout": "Как расположена касса: горизонтально или вертикально?",
    "width": "Какая ширина чековой ленты: 80 или 58 мм?",
    "model": "Какая модель указана на кассе: Вики Принт, Пирит 2Ф или АТОЛ FPrint-22ПТК? Если не можете посмотреть, так и напишите.",
    "symptom": "Что происходит: бумага совсем не выходит, выходит пустой чек или на чеке нет только QR-кода?",
    "paper": "Бумага в кассе есть? Посмотрите также, горит ли индикатор «Бумага». Ничего разбирать не нужно.",
    "error": "Какой текст ошибки на экране или какие индикаторы горят? Если ошибки нет или не можете прочитать — напишите это.",
}


def applies(state, message):
    return bool(
        state.get("_receipt")
        or re.search(
            r"\bчек\b|пуст\w* чек|не\s*печат|не\s*выходит.*(?:чек|бумаг)|касс\w*.*(?:слом|не работает)|ничего.*не работает",
            message,
            re.I,
        )
    )


def model_name(message):
    candidates = model_candidates(normalize(message))
    return candidates[0][1] if len({value for _, value in candidates}) == 1 else None


def handoff(state, reason):
    state.update(_phase="confirm", unknowns=[reason])
    state.get("_receipt", {}).pop("pending", None)
    return (
        state,
        reason + "\n\nПередать обращение специалисту вместе с вашими ответами?",
    )


def ask(state, field, question=None):
    flow = state["_receipt"]
    flow["question_revision"] = flow.get("question_revision", 0) + 1
    flow.update(pending=field, question=question or QUESTIONS[field])
    return state, flow["question"]


async def respond_receipt(state, message, lookup, timeout=45):
    state = deepcopy(state)
    flow = state.setdefault("_receipt", {})
    pending = flow.pop("pending", None)
    text = normalize(message).strip(" .!?")
    state.setdefault("problem", message)
    state.update(_engine="rules", _phase="diagnosing")
    observations = state.setdefault("observations", [])
    observations.append(
        {"question": flow.get("question", "Описание проблемы"), "answer": message}
    )
    state["observations"] = observations[-30:]
    update = collect_facts(flow, message, pending)
    facts = flow["facts"]
    state["receipt_facts"] = deepcopy(facts)
    if "model" in update.changed:
        state["environment"] = facts.get("model") or "Модель неизвестна"
    if update.changed & SELECTION_FACTS:
        state.pop("sources", None)
        state.pop("unknowns", None)
        state.pop("hypotheses", None)
        state.pop("check_result", None)
        flow.pop("active_procedure", None)
        state.pop("resolution", None)
    if re.search(r"перезагруз|перезапус|пробовал|проверял", text):
        state["attempts"] = message
    if update.conflicts:
        field = next(
            (
                key
                for key in (
                    "model",
                    "paper_present",
                    "symptom",
                    "layout",
                    "paper_width_mm",
                )
                if key in update.conflicts
            ),
            sorted(update.conflicts)[0],
        )
        step = next((key for key, value in ALIASES.items() if value == field), field)
        if pending == step and flow.get("conflict_asked") == field:
            return handoff(
                state,
                "Противоречивые сведения не удалось уточнить. Сохраним их для специалиста.",
            )
        flow["conflict_asked"] = field
        return ask(
            state,
            step,
            "В ответах есть противоречие. "
            + QUESTIONS.get(step, "Уточните значение: " + field),
        )
    flow.pop("conflict_asked", None)
    outcome = check_result(message) if pending == "result" else {}
    if pending == "result" and (outcome or not update.changed & SELECTION_FACTS):
        state["check_result"] = message
        if outcome.get("problem_resolved") is True:
            state.update(_phase="resolved", resolution=message)
            facts["problem_resolved"] = True
            state["receipt_facts"] = deepcopy(facts)
            return state, "Отлично, печать восстановлена. Обращение завершено."
        facts.update(outcome)
        facts.setdefault("problem_resolved", None)
        state["receipt_facts"] = deepcopy(facts)
        return handoff(
            state,
            "Проверка не подтвердила решение. Передадим результат специалисту без повторения тех же действий.",
        )
    if pending == "error" and "введу текст" in text:
        return ask(
            state,
            "error",
            "Напишите сообщение или код ошибки так, как он показан на экране.",
        )
    if facts.get("error_status"):
        state["check_result"] = (
            "Рулон: "
            + (flow.get("paper") or "unknown")
            + "\nСообщение устройства: "
            + (flow.get("error") or "Неизвестно")
        )
    required = ["model", "symptom"]
    if flow.get("symptom") != "не печатается QR-код":
        required.append("paper")
        if not flow.get("paper_missing"):
            required.append("error")
    if flow.get("paper_missing") and flow.get("model") == "АТОЛ FPrint-22ПТК":
        required.extend(["layout", "width"])
    for field in required:
        canonical = ALIASES.get(field, field)
        if flow.get(field):
            continue
        if canonical in facts and facts[canonical] is None:
            return handoff(
                state,
                "Не удалось определить обязательные сведения: " + QUESTIONS[field],
            )
        retries = flow.setdefault("question_retries", {})
        if pending == field:
            retries[field] = retries.get(field, 0) + 1
            if retries[field] >= 2:
                facts[canonical] = None
                state["receipt_facts"] = deepcopy(facts)
                return handoff(
                    state,
                    "Не удалось однозначно понять ответ. Сохраним сведения для специалиста.",
                )
        question = QUESTIONS[field]
        if field == "model" and re.search(r"атол", text):
            question = "АТОЛ — это производитель. На наклейке указано FPrint-22ПТК или другая модель?"
        return ask(state, field, question)
    if lookup is None:
        return (
            state,
            "Поиск по инструкциям пока загружается. Данные сохранены; напишите «продолжить» через минуту.",
        )
    query = (
        f"Как заправить чековую ленту в {flow['model']}?"
        if flow.get("paper_missing")
        else f"{flow['model']}: {flow['symptom']}. Рулон: {flow.get('paper', 'unknown')}. Сообщение устройства: {flow.get('error', '')}. Какие проверки описаны в инструкции?"
    )
    try:
        result = await asyncio.wait_for(lookup(query, flow), timeout=timeout)
    except Exception:
        logger.exception("Receipt knowledge lookup failed")
        return (
            state,
            "Не удалось получить инструкцию. Данные сохранены; попробуйте «продолжить» или выберите специалиста.",
        )
    if result.get("status") == "loading":
        return (
            state,
            "Поиск по инструкциям ещё загружается. Ответы сохранены; напишите «продолжить» через минуту.",
        )
    answer = result.get("answer") or ""
    sources = result.get("sources") or []
    if result.get("status") != "answered" or not sources:
        return handoff(
            state,
            "Подходящая инструкция не найдена. Не будем угадывать причину поломки.",
        )
    state["sources"] = sources
    links = "\n".join(f"{source['title']}: {source['url']}" for source in sources)
    evidence = (answer + "\n\n" if answer else "") + "Источники:\n" + links
    if result.get("kind") != "instruction":
        reason = (
            result.get("reason")
            or "Применимая инструкция по устранению проблемы не найдена."
        )
        return handoff(state, evidence + "\n\n" + reason)
    flow["question_revision"] = flow.get("question_revision", 0) + 1
    flow.update(
        pending="result", question="После выполнения инструкции чек печатается?"
    )
    state["attempts"] = (
        state.get("attempts", "") + "\nПредложена инструкция: " + query
    ).strip()
    links = "\n".join(f"{source['title']}: {source['url']}" for source in sources)
    return (
        state,
        answer
        + "\n\nИсточники:\n"
        + links
        + "\n\nПосле выполнения инструкции чек печатается?",
    )
