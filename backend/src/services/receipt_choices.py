"""Stable choices for the receipt dialogue; the server validates the current step."""

OPTIONS = {
    "model": [
        ("atol", "АТОЛ FPrint-22ПТК"),
        ("pirit", "Пирит 2Ф"),
        ("viki", "Вики Принт"),
        ("unknown", "Другая модель / не знаю"),
    ],
    "symptom": [
        ("none", "Бумага не выходит"),
        ("blank", "Выходит пустой чек"),
        ("qr", "Нет QR-кода"),
        ("other", "Другое — опишу"),
    ],
    "paper": [
        ("yes", "Бумага есть"),
        ("no", "Бумаги нет"),
        ("unknown", "Не могу проверить"),
    ],
    "error": [
        ("none", "Ошибки нет"),
        ("text", "Есть ошибка — введу текст"),
        ("unknown", "Не могу прочитать"),
    ],
    "layout": [
        ("horizontal", "Горизонтально"),
        ("vertical", "Вертикально"),
        ("unknown", "Не знаю"),
    ],
    "width": [("80", "80 мм"), ("58", "58 мм"), ("unknown", "Не знаю")],
    "result": [
        ("yes", "Да, помогло"),
        ("no", "Не помогло"),
        ("unknown", "Не удалось выполнить"),
    ],
}


def choices_for(state):
    if state.get("_phase") in {"confirm", "resolved", "cancelled", "ticket_created"}:
        return []
    step = state.get("_receipt", {}).get("pending")
    revision = state.get("_receipt", {}).get("question_revision", 0)
    options = state.get("_receipt", {}).get("question_options")
    if options is not None:
        return [
            {"id": f"{step}:{index}:{revision}", "label": option["label"]}
            for index, option in enumerate(options)
        ]
    return [
        {"id": f"{step}:{key}:{revision}", "label": label}
        for key, label in OPTIONS.get(step, [])
    ]


def choice_fact(state, choice_id):
    options = state.get("_receipt", {}).get("question_options")
    if options is None:
        return None
    choices = choices_for(state)
    for index, choice in enumerate(choices):
        if choice["id"] == choice_id:
            return {
                "field": state["_receipt"]["pending"],
                "value": options[index]["value"],
            }
    return None
