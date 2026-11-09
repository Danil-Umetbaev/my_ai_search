"""Select a single applicable section from retrieved source documents."""
import re

PAPER_SECTIONS = {
    "Пирит 2Ф": "Пирит 2Ф — Порядок замены (установки) термобумаги",
    "Вики Принт": "Вики Принт не печатает документы",
    "АТОЛ FPrint-22ПТК": "FPrint-22ПТК — Заправка бумаги",
}


def between(content, start, end):
    match = re.search(start + r"(.*?)" + end, content, re.I | re.S)
    return match[1].strip() if match else None


def select_instruction(result, documents, flow):
    if not flow.get("paper_missing"):
        return classify_answer(result, flow)
    for source, content in documents:
        title = source["title"].casefold()
        answer = None
        if flow["model"] == "Пирит 2Ф" and "термобумаги" in title:
            answer = between(content, r"термобумаги в ККТ", r"## 8\.")
        elif flow["model"] == "Вики Принт" and "вики принт не печатает" in title:
            # This section supports a paper-presence check, not a repair diagnosis.
            match = re.search(r"Убедитесь, что бумага вставлена в отсек для бумаги\.", content)
            answer = match[0] if match else None
        elif flow["model"] == "АТОЛ FPrint-22ПТК" and "заправка бумаги" in title:
            if flow.get("width") == "58":
                # The manual gives a separate limiter procedure; do not mix it with 80 mm.
                answer = between(content, r"При использовании ЧЛ шириной 58 мм", r"В случае остановки")
                if answer:
                    answer = "При использовании ЧЛ шириной 58 мм " + answer
            elif flow.get("layout") == "vertical":
                answer = between(content, r"используется ось для бумаги:", r"Рисунок 10")
            else:
                answer = between(content, r"При использовании ЧЛ шириной 80 мм необходимо выполнить следующие действия\.", r"Рисунок 9")
            if answer:
                warning = re.search(r"Запрещается открывать крышку во время печати\..*?Не допускается установка неплотно намотанных рулонов бумаги\.", content, re.S)
                if warning:
                    answer += "\n\n" + warning[0]
        if answer:
            answer = re.sub(r"Рисунок \d+[^\n]*", "", answer)
            answer = re.sub(r"(?m)^\s*(?:\d+\s+){2,}\d*\s*$", "", answer)
            return {**result, "status": "answered", "answer": answer.strip(), "sources": [source], "kind": "instruction"}
    # A broad answer is not a substitute for the missing installation section.
    return {**result, "status": "not_found", "answer": None, "sources": []}


def clean_answer(answer):
    paragraphs = re.split(r"\n\s*\n", answer.strip())
    result = []
    seen = set()
    for paragraph in paragraphs:
        key = re.sub(r"[\W_]+", "", paragraph.casefold())
        if key and key not in seen:
            result.append(paragraph.strip())
            seen.add(key)
    return "\n\n".join(result)


def classify_answer(result, flow):
    """A retrieved explanation is evidence, but not necessarily an executable action."""
    answer = clean_answer(result.get("answer") or "")
    if result.get("status") != "answered" or not result.get("sources"):
        return {**result, "kind": "missing"}
    reason = None
    if re.search(r"файл\w* с макросом", answer, re.I) and not re.search(
        r"[\w.-]+\.(?:txt|xml|mac|fito|zip)\b", answer, re.I
    ):
        return {
            **result, "kind": "incomplete",
            "answer": "В статье для этой проблемы описан запуск макроса через Fito и последующий рестарт ККТ. В загруженном тексте не указан конкретный файл макроса, поэтому выполнить инструкцию однозначно нельзя.",
            "reason": "Нужно уточнить файл макроса у специалиста; случайный файл выбирать не следует.",
        }
    if len(answer) > 2400:
        return {**result, "kind": "incomplete", "answer": "",
                "reason": "Найдены общие материалы, но не выделена инструкция именно для описанного случая."}
    if re.search(r"вскр|разбер|открут|шлейф|плат[уы]|сброс|прошив|замкн|перерегистр|замен\w* ФН|открыть чек|закрыть чек|чек прихода", answer, re.I):
        return {**result, "kind": "incomplete", "answer": "",
                "reason": "Найденный материал включает сервисные или фискальные операции. Применимость должен проверить специалист."}
    action = re.search(
        r"\b(?:откройте|закройте|установите|нажмите|проверьте|убедитесь|вставьте|выключите|включите|запустите|перейдите|выберите|удалите|оторвите|нажать|открыть|закрыть|установить|проверить)\b", answer, re.I
    )
    if not action:
        reason = "Это справочное описание, а не инструкция по устранению вашей неисправности."
        if flow.get("paper") == "present" and re.search(r"нет бумаги|бумага отсутствует|отсутствует бумага", answer, re.I):
            reason = "Вы уже указали, что рулон установлен. Описание индикатора не объясняет причину этого расхождения; подходящая проверка не найдена."
    return {**result, "answer": answer, "kind": "information" if reason else "instruction", "reason": reason}
