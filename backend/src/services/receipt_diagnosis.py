"""Bounded receipt triage; repair instructions come only from the knowledge base."""
import asyncio
import logging
import re
from copy import deepcopy


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
    return bool(state.get("_receipt") or re.search(
        r"\bчек\b|пуст\w* чек|не\s*печат|не\s*выходит.*(?:чек|бумаг)|касс\w*.*(?:слом|не работает)|ничего.*не работает", message, re.I,
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
    return state, reason + "\n\nПередать обращение специалисту вместе с вашими ответами?"


async def respond_receipt(state, message, lookup, timeout=45):
    state = deepcopy(state)
    flow = state.setdefault("_receipt", {})
    text = message.strip().casefold().replace("ё", "е")
    text = re.sub(r"бамаг", "бумаг", text)
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
    # Device error text does not replace a physical observation.
    if pending != "error" and not re.search(r"ошибк|пишет|сообщение", text):
        if re.search(r"бумаг\w* нет|нет бумаг|бумага закончилась", text):
            flow.update(paper="absent", paper_missing=True)
        elif re.search(r"бумага есть|рулон установлен", text):
            flow.update(paper="present", paper_missing=False)
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
        if not flow.get("retried_" + pending) and not re.search(r"не знаю|не могу|не понимаю", text):
            flow["retried_" + pending] = True
            question = QUESTIONS[pending]
            if pending == "model" and re.search(r"атол", text):
                question = "АТОЛ — это производитель. На наклейке указано FPrint-22ПТК или другая модель?"
            flow.update(pending=pending, question=question)
            return state, question
        return handoff(state, "Не удалось определить модель или характер неисправности. Специалисту понадобится уточнение.")
    if pending == "paper":
        if re.search(r"не могу|не знаю|не понимаю", text):
            return handoff(state, "Не удалось проверить наличие рулона.")
        if re.fullmatch(r"(?:да|есть)[.! ]*", text):
            flow.update(paper="present", paper_missing=False)
        elif re.fullmatch(r"нет[.! ]*", text):
            flow.update(paper="absent", paper_missing=True)
        if not flow.get("paper"):
            flow.update(pending="paper", question=QUESTIONS["paper"])
            return state, "Не понял, установлен ли рулон. Выберите вариант ниже или уточните ответ."
    if pending == "error":
        if "введу текст" in text:
            flow.update(pending="error", question=QUESTIONS["error"])
            return state, "Напишите сообщение или код ошибки так, как он показан на экране."
        flow["error"] = message
        state["check_result"] = "Рулон: " + flow.get("paper", "unknown") + "\nСообщение устройства: " + message
    if pending in {"layout", "width"}:
        if "не знаю" in text:
            return handoff(state, "Для выбора варианта установки бумаги нужно определить расположение кассы и ширину ленты.")
        if pending == "layout":
            if "горизонт" in text: flow["layout"] = "horizontal"
            elif "вертик" in text: flow["layout"] = "vertical"
        elif re.search(r"\b(58|80)\b", text):
            flow["width"] = re.search(r"\b(58|80)\b", text)[1]
    required = ["model", "symptom"]
    if flow.get("symptom") != "не печатается QR-код":
        required.append("paper")
        if not flow.get("paper_missing"):
            required.append("error")
    if flow.get("paper_missing") and flow.get("model") == "АТОЛ FPrint-22ПТК":
        required.extend(["layout", "width"])
    for field in required:
        if not flow.get(field):
            flow.update(pending=field, question=QUESTIONS[field])
            return state, QUESTIONS[field]
    if lookup is None:
        return state, "Поиск по инструкциям пока загружается. Данные сохранены; напишите «продолжить» через минуту."
    query = (
        f"Как заправить чековую ленту в {flow['model']}?" if flow.get("paper_missing") else
        f"{flow['model']}: {flow['symptom']}. Рулон: {flow.get('paper', 'unknown')}. Сообщение устройства: {flow.get('error', '')}. Какие проверки описаны в инструкции?"
    )
    try:
        result = await asyncio.wait_for(lookup(query, flow), timeout=timeout)
    except Exception:
        logger.exception("Receipt knowledge lookup failed")
        return state, "Не удалось получить инструкцию. Данные сохранены; попробуйте «продолжить» или выберите специалиста."
    if result.get("status") == "loading":
        return state, "Поиск по инструкциям ещё загружается. Ответы сохранены; напишите «продолжить» через минуту."
    answer = result.get("answer") or ""
    sources = result.get("sources") or []
    if result.get("status") != "answered" or not sources:
        return handoff(state, "Подходящая инструкция не найдена. Не будем угадывать причину поломки.")
    state["sources"] = sources
    links = "\n".join(f"{source['title']}: {source['url']}" for source in sources)
    evidence = (answer + "\n\n" if answer else "") + "Источники:\n" + links
    if result.get("kind") != "instruction":
        reason = result.get("reason") or "Применимая инструкция по устранению проблемы не найдена."
        return handoff(state, evidence + "\n\n" + reason)
    flow.update(pending="result", question="После выполнения инструкции чек печатается?")
    state["attempts"] = (state.get("attempts", "") + "\nПредложена инструкция: " + query).strip()
    links = "\n".join(f"{source['title']}: {source['url']}" for source in sources)
    return state, answer + "\n\nИсточники:\n" + links + "\n\nПосле выполнения инструкции чек печатается?"
