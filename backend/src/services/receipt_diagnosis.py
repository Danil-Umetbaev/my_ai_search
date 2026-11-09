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
    legacy_facts,
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
        or model_candidates(normalize(message))
        or re.search(
            r"\bчек\b|пуст\w* чек|не\s*печат|не\s*выходит.*(?:чек|бумаг)|касс\w*.*(?:слом|не работает|не отвечает)|(?:бумаг|лент)\w*.*(?:замя|застря)|ничего.*не работает",
            message,
            re.I,
        )
    )


def model_name(message):
    candidates = model_candidates(normalize(message))
    return candidates[0][1] if len({value for _, value in candidates}) == 1 else None


def handoff(state, reason):
    state.update(_phase="confirm", unknowns=[reason], next_action="offer_specialist")
    state.get("_receipt", {}).pop("pending", None)
    state.get("_receipt", {}).pop("active_procedure", None)
    return (
        state,
        reason + "\n\nПередать обращение специалисту вместе с вашими ответами?",
    )


def ask(state, field, question=None):
    flow = state["_receipt"]
    flow["question_revision"] = flow.get("question_revision", 0) + 1
    flow.pop("question_options", None)
    flow.update(pending=field, question=question or QUESTIONS[field])
    state["next_action"] = (
        "ask_result" if field in {"result", "procedure_result"} else "ask_fact"
    )
    return state, flow["question"]


def search_unavailable(state):
    state.update(next_action="retry_search", search_status="unavailable")
    return (
        state,
        "Поиск временно недоступен. Ваши ответы сохранены. Повторите запрос или выберите специалиста; сейчас нельзя определить, есть ли подходящий ответ в базе.",
    )


async def respond_receipt(state, message, lookup, timeout=45, selected_fact=None):
    state = deepcopy(state)
    flow = state.setdefault("_receipt", {})
    pending = flow.pop("pending", None)
    active_procedure = flow.get("active_procedure")
    result_action = flow.get("result_action")
    text = normalize(message).strip(" .!?")
    historical_problem = state.get("problem")
    state.setdefault("problem", message)
    if not flow.get("problem_facts_loaded"):
        if historical_problem and historical_problem != message:
            initial = {}
            collect_facts(initial, historical_problem)
            facts = legacy_facts(flow)
            for key, value in initial["facts"].items():
                facts.setdefault(key, value)
        flow["problem_facts_loaded"] = True
    if state.get("_phase") == "informed" and text in {
        "спасибо",
        "понятно",
        "ок",
        "хорошо",
    }:
        return state, "Пожалуйста. Если появится другой вопрос по кассе, напишите его."
    if state.get("_phase") == "informed":
        state["problem"] = message
        state.pop("reference_id", None)
    state.update(_engine="rules", _phase="diagnosing")
    observations = state.setdefault("observations", [])
    observations.append(
        {"question": flow.get("question", "Описание проблемы"), "answer": message}
    )
    state["observations"] = observations[-30:]
    result_field = (
        {
            "collect_paper_presence": "paper_present",
            "collect_connection_result": "fito_connected",
            "collect_print_setting": "print_disabled",
        }.get(result_action)
        if pending == "procedure_result"
        else None
    )
    update = collect_facts(flow, message, result_field or pending, selected_fact)
    facts = flow["facts"]
    state["receipt_facts"] = deepcopy(facts)
    if (
        pending not in {"result", "procedure_result"}
        and re.search(
            r"чек.{0,30}печата|проблема.{0,20}(?:решена|исчезла|устранена)", text
        )
        and check_result(message).get("problem_resolved") is True
    ):
        facts["problem_resolved"] = True
        state.update(
            _phase="resolved",
            next_action="close_resolved",
            resolution=message,
            receipt_facts=deepcopy(facts),
        )
        flow.pop("active_procedure", None)
        return (
            state,
            "Вы подтвердили, что проблема решена. Обращение завершено без заявки специалисту.",
        )
    if "model" in update.changed:
        flow.pop("completed_procedures", None)
        state["environment"] = facts.get("model") or "Модель неизвестна"
    if update.changed & SELECTION_FACTS:
        state.pop("sources", None)
        state.pop("retrieved_materials", None)
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
    if (
        active_procedure
        and pending in {"result", "procedure_result"}
        and not update.changed & SELECTION_FACTS
        and re.search(r"уточняю|без опечаток", text)
        and lookup is not None
    ):
        try:
            verified = await asyncio.wait_for(lookup(message, flow), timeout=timeout)
        except Exception:
            logger.exception("Procedure acknowledgement lookup failed")
            flow["pending"] = pending
            return search_unavailable(state)
        if verified.get("status") == "blocked":
            return handoff(state, verified["reason"])
        if verified.get("procedure_id") == active_procedure:
            flow["pending"] = pending
            state["next_action"] = "acknowledge_existing_plan"
            return (
                state,
                "Уточнение принято. Ранее предложенная инструкция остаётся применимой.\n\n"
                + flow["question"],
            )
    if active_procedure and re.search(
        r"(?:фото|схем\w*|рисунок|файл).{0,30}(?:не открыва|недоступ|не загру)|не могу открыть.{0,20}(?:фото|схем|файл)",
        text,
    ):
        return handoff(
            state,
            "Обязательный материал инструкции недоступен. Продолжать по догадке нельзя; специалист поможет проверить материал и следующий шаг.",
        )
    outcome = check_result(message) if pending == "result" else {}
    if (
        pending == "result"
        and "model" not in update.changed
        and (outcome or not update.changed & SELECTION_FACTS)
    ):
        if not outcome:
            if active_procedure and lookup is not None:
                try:
                    verified = await asyncio.wait_for(
                        lookup(state["problem"], flow), timeout=timeout
                    )
                except Exception:
                    logger.exception("Active procedure verification failed")
                    flow["pending"] = "result"
                    return search_unavailable(state)
                if verified.get("status") == "blocked":
                    return handoff(state, verified["reason"])
                if verified.get("status") in {"loading", "error", "unavailable"}:
                    flow["pending"] = "result"
                    return search_unavailable(state)
            retries = flow.setdefault("question_retries", {})
            retries["result"] = retries.get("result", 0) + 1
            if retries["result"] < 2:
                return ask(
                    state,
                    "result",
                    "Удалось выполнить инструкцию и устранить исходную проблему? Можно ответить: «помогло», «не помогло» или «не смог выполнить».",
                )
        if active_procedure:
            flow.setdefault("completed_procedures", []).append(active_procedure)
        state["check_result"] = message
        if outcome.get("problem_resolved") is True:
            state.update(
                _phase="resolved", resolution=message, next_action="close_resolved"
            )
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
    if pending == "procedure_result" and "model" not in update.changed:
        state["check_result"] = message
        if active_procedure:
            flow.setdefault("completed_procedures", []).append(active_procedure)
            flow.pop("active_procedure", None)
        outcome = (
            check_result(message)
            if re.search(
                r"чек.{0,30}печата|проблема.{0,20}(?:решена|исчезла|устранена)", text
            )
            else {}
        )
        if outcome.get("problem_resolved") is True:
            facts.update(outcome)
            state["receipt_facts"] = deepcopy(facts)
            state.update(
                _phase="resolved", resolution=message, next_action="close_resolved"
            )
            return state, "Решение исходной проблемы подтверждено. Обращение завершено."
        if not result_field or facts.get(result_field) is None:
            return handoff(
                state,
                "Результат проверки сохранён. Он сам по себе не подтверждает устранение неисправности; передадим сведения специалисту.",
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
    if lookup is not None:
        required = ["model"]
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
        return search_unavailable(state)
    query = state["problem"] + "\n" + message
    if flow.get("symptom"):
        query += "\nТекущий симптом: " + flow["symptom"]
    try:
        result = await asyncio.wait_for(lookup(query, flow), timeout=timeout)
    except Exception:
        logger.exception("Receipt knowledge lookup failed")
        return search_unavailable(state)
    state["search_status"] = "available"
    if result.get("status") == "clarify":
        field = result["field"]
        retries = flow.setdefault("question_retries", {})
        if pending == field:
            retries[field] = retries.get(field, 0) + 1
            if retries[field] >= 2:
                facts[field] = None
                state["receipt_facts"] = deepcopy(facts)
                return handoff(
                    state,
                    "Не удалось уточнить обязательное условие. Передадим сведения специалисту.",
                )
        state, question = ask(state, field, result["question"])
        flow["question_options"] = result["choices"]
        return state, question
    if result.get("status") == "blocked":
        return handoff(state, result["reason"])
    if result.get("materials"):
        state["retrieved_materials"] = result["materials"]
    if result.get("status") in {"loading", "error", "unavailable"}:
        return search_unavailable(state)
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
    if result.get("kind") not in {"instruction", "diagnostic_check"}:
        flow.pop("pending", None)
        flow.pop("active_procedure", None)
        flow.pop("question_options", None)
        state["reference_id"] = result.get("reference_id")
        if result.get("reason"):
            state, answer = handoff(state, evidence + "\n\n" + result["reason"])
            state["next_action"] = "explain_and_offer_specialist"
            return state, answer
        state.update(_phase="informed", next_action="explain_information")
        return state, evidence
    flow["question_revision"] = flow.get("question_revision", 0) + 1
    flow.pop("question_options", None)
    question = result.get(
        "result_question", "После выполнения инструкции чек печатается?"
    )
    flow.update(
        pending="result" if result.get("kind") == "instruction" else "procedure_result",
        question=question,
        active_procedure=result.get("procedure_id"),
        result_action=result.get("result_action"),
    )
    state.update(next_action="offer_procedure", procedure_id=result.get("procedure_id"))
    state["attempts"] = (
        state.get("attempts", "") + "\nПредложена инструкция: " + query
    ).strip()
    links = "\n".join(f"{source['title']}: {source['url']}" for source in sources)
    return (
        state,
        answer + "\n\nИсточники:\n" + links + "\n\n" + question,
    )
