"""Bounded receipt triage; repair instructions come only from the knowledge base."""
import asyncio
import logging
import re
from copy import deepcopy

from src.services.diagnosis import summary

logger = logging.getLogger(__name__)
QUESTIONS = {
    "model": "Какая модель указана на кассе: Вики Принт, Пирит 2Ф или АТОЛ FPrint-22ПТК? Если не можете посмотреть, так и напишите.",
    "symptom": "Что происходит: бумага совсем не выходит, выходит пустой чек или на чеке нет только QR-кода?",
    "paper": "Бумага в кассе есть? Посмотрите также, горит ли индикатор «Бумага». Ничего разбирать не нужно.",
    "error": "Какой текст ошибки на экране или какие индикаторы горят? Если ошибки нет или не можете прочитать — напишите это.",
}


def applies(state, message):
    return bool(state.get("_receipt") or re.search(
        r"не\s*печат|не\s*выходит.*(?:чек|бумаг)|касс\w*.*(?:слом|не работает)", message, re.I,
    ))


def model_name(message):
    if re.search(r"вики\s*принт|viki\s*print", message, re.I):
        return "Вики Принт"
    if re.search(r"пирит\s*2\s*[фf]", message, re.I):
        return "Пирит 2Ф"
    if re.search(r"(?:fprint|фпринт|атол)\s*[- ]?\s*22", message, re.I):
        return "АТОЛ FPrint-22ПТК"
    return None


def handoff(state, reason):
    state.update(_phase="confirm", unknowns=[reason])
    return state, reason + "\n\n" + summary(state)


async def respond_receipt(state, message, lookup, timeout=45):
    state = deepcopy(state)
    flow = state.setdefault("_receipt", {})
    text = message.strip().casefold().replace("ё", "е")
    state.setdefault("problem", message)
    state.update(_engine="rules", _phase="diagnosing")
    observations = state.setdefault("observations", [])
    observations.append({"question": flow.get("question", "Описание проблемы"), "answer": message})
    state["observations"] = observations[-30:]
    pending = flow.pop("pending", None)
    detected = model_name(message)
    if detected:
        flow["model"] = detected
        state["environment"] = message
    if re.search(r"перезагруз|перезапус|пробовал|проверял", text):
        state["attempts"] = message
    if re.search(r"qr|куар", text):
        flow["symptom"] = "не печатается QR-код"
    elif re.search(r"пуст\w* (?:чек|бумаг)|бел\w* (?:чек|бумаг)", text):
        flow["symptom"] = "выходит пустой чек"
    elif re.search(r"не печат|совсем не выходит|бумага не выходит", text):
        flow["symptom"] = "чек не печатается"
    if pending == "result":
        state["check_result"] = message
        if re.fullmatch(r"(?:да|помогло|да[, ]+помогло|печатает|заработало|все работает)[.! ]*", text):
            state.update(_phase="resolved", resolution=message)
            return state, "Отлично, печать восстановлена. Обращение завершено."
        return handoff(state, "Проверка не подтвердила решение. Передадим результат специалисту без повторения тех же действий.")
    if pending in {"model", "symptom"} and not flow.get(pending):
        return handoff(state, "Не удалось определить модель или характер неисправности. Специалисту понадобится уточнение.")
    if pending == "paper":
        flow["paper"] = message
        state["check_result"] = message
        flow["paper_missing"] = bool(re.search(r"бумаг\w* нет|нет бумаг|закончилась|^нет[.! ]*$", text))
    if pending == "error":
        flow["error"] = message
        state["check_result"] = (state.get("check_result", "") + "\nОшибка/индикаторы: " + message).strip()
    required = ["model", "symptom"]
    if flow.get("symptom") != "не печатается QR-код":
        required.append("paper")
        if not flow.get("paper_missing"):
            required.append("error")
    for field in required:
        if not flow.get(field):
            flow.update(pending=field, question=QUESTIONS[field])
            return state, QUESTIONS[field]
    if lookup is None:
        return state, "Поиск по инструкциям пока загружается. Данные сохранены; напишите «продолжить» через минуту."
    query = (
        f"Как заправить чековую ленту в {flow['model']}?" if flow.get("paper_missing") else
        f"{flow['model']}: {flow['symptom']}. {flow.get('error', '')} Какие проверки описаны в инструкции?"
    )
    try:
        result = await asyncio.wait_for(lookup(query), timeout=timeout)
    except Exception:
        logger.exception("Receipt knowledge lookup failed")
        return state, "Не удалось получить инструкцию. Данные сохранены; попробуйте «продолжить» или выберите специалиста."
    answer = result.get("answer") or ""
    sources = result.get("sources") or []
    if result.get("status") != "answered" or not sources:
        return handoff(state, "Подходящая инструкция не найдена. Не будем угадывать причину поломки.")
    if re.search(r"вскр|разбер|открут|шлейф|плат[уы]|сброс|прошив|замкн|повтор\w* оплат", answer, re.I):
        return handoff(state, "Найденная инструкция затрагивает сервисные работы. Дальнейшую диагностику лучше выполнить специалисту.")
    state["sources"] = sources
    flow.update(pending="result", question="После выполнения инструкции чек печатается?")
    state["attempts"] = (state.get("attempts", "") + "\nПредложена инструкция: " + query).strip()
    links = "\n".join(f"{source['title']}: {source['url']}" for source in sources)
    return state, answer + "\n\nИсточники:\n" + links + "\n\nПосле выполнения инструкции чек печатается?"
