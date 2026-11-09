"""Select a single applicable section from retrieved source documents."""
import re


def between(content, start, end):
    match = re.search(start + r"(.*?)" + end, content, re.I | re.S)
    return match[1].strip() if match else None


def select_instruction(result, documents, flow):
    if not flow.get("paper_missing"):
        return result
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
            return {**result, "status": "answered", "answer": answer.strip(), "sources": [source]}
    # A broad answer is not a substitute for the missing installation section.
    return {**result, "status": "not_found", "answer": None, "sources": []}
