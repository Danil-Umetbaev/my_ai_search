"""Stable choices for the receipt dialogue; the server validates the current step."""
OPTIONS = {
    "model": [("atol", "АТОЛ FPrint-22ПТК"), ("pirit", "Пирит 2Ф"), ("viki", "Вики Принт"), ("unknown", "Другая модель / не знаю")],
    "symptom": [("none", "Бумага не выходит"), ("blank", "Выходит пустой чек"), ("qr", "Нет QR-кода"), ("other", "Другое — опишу")],
    "paper": [("yes", "Бумага есть"), ("no", "Бумаги нет"), ("unknown", "Не могу проверить")],
    "error": [("none", "Ошибки нет"), ("text", "Есть ошибка — введу текст"), ("unknown", "Не могу прочитать")],
    "layout": [("horizontal", "Горизонтально"), ("vertical", "Вертикально"), ("unknown", "Не знаю")],
    "width": [("80", "80 мм"), ("58", "58 мм"), ("unknown", "Не знаю")],
    "result": [("yes", "Да, помогло"), ("no", "Не помогло"), ("unknown", "Не удалось выполнить")],
}


def choices_for(state):
    if state.get("_phase") in {"confirm", "resolved", "cancelled", "ticket_created"}:
        return []
    step = state.get("_receipt", {}).get("pending")
    return [{"id": f"{step}:{key}", "label": label} for key, label in OPTIONS.get(step, [])]
