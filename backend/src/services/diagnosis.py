import re
from copy import deepcopy

PROMPTS = {
    "problem": "Что именно не работает? Укажите текст ошибки, если он есть. Не отправляйте пароли и коды подтверждения.",
    "environment": "Уточните магазин, номер кассы или устройство и версию программы, если знаете.",
    "impact": "Когда началось, сколько рабочих мест затронуто и можно ли продолжать работу?",
    "attempts": "Что уже проверили и с каким результатом? Если ничего — так и напишите.",
}
BRANCHES = (
    (
        "payment",
        r"оплат|эквайр|терминал|банков|карт[аоы]",
        "Что показывает платёжный терминал и каков статус операции? Если деньги могли списаться, не повторяйте оплату до проверки.",
    ),
    (
        "receipt",
        r"чек|принтер|фискал|ккт|офд",
        "Проверьте наличие бумаги и индикаторы принтера без разборки устройства. Какие индикаторы горят и какой текст ошибки отображается?",
    ),
    (
        "network",
        r"сеть|сет[ьи]|интернет|соединен|сервер.*недоступ|тайм.?аут",
        "Открывается ли известный рабочий внутренний ресурс на этом и соседнем рабочем месте? Сообщите результат; настройки сети пока не меняйте.",
    ),
    (
        "login",
        r"вход|войти|парол|авторизац|доступ",
        "Ошибка входа только у вас или у коллег тоже? Укажите текст ошибки. Пароль и коды подтверждения не отправляйте.",
    ),
)
LABELS = {
    "problem": "Проблема",
    "environment": "Окружение",
    "impact": "Влияние",
    "attempts": "Проверки",
    "check_result": "Результат диагностики",
    "additional_context": "Дополнение",
    "hypotheses": "Гипотезы (не подтверждены)",
    "unknowns": "Неизвестные сведения",
}


def is_ready(state):
    return state.get("_phase") == "confirm" or (
        "_phase" not in state and all(state.get(field) for field in PROMPTS)
    )


def ticket_details(state):
    details = deepcopy(
        {key: value for key, value in state.items() if not key.startswith("_")}
    )
    flow = state.get("_receipt", {})
    for key in ("fact_changes", "completed_procedures"):
        if flow.get(key):
            details[key] = deepcopy(flow[key])
    return details


def summary(state):
    return (
        "Сводка заявки:\n"
        + "\n".join(
            f"{label}: {state[key]}" for key, label in LABELS.items() if state.get(key)
        )
        + "\nОтправить специалисту? Ответьте «да». Для исправления: «проблема: …», «окружение: …», «влияние: …», «проверки: …». Можно написать «отмена»."
    )


def advance(state, message):
    state = deepcopy(state)
    content = message.strip()
    normalized = content.casefold().replace("ё", "е").rstrip(".!?")
    if not content:
        return state, "Введите описание или ответ на вопрос.", is_ready(state)
    if normalized in {"отмена", "отменить"}:
        state["_phase"] = "cancelled"
        return (
            state,
            "Обращение отменено. Заявка не создана. Завершите диалог, чтобы начать заново.",
            False,
        )
    if state.get("_phase") == "cancelled":
        return state, "Диалог отменён. Начните новый диалог для обращения.", False
    if state.get("_phase") == "resolved":
        return (
            state,
            "Обращение завершено. Начните новый диалог, если нужна помощь.",
            False,
        )
    if is_ready(state):
        if normalized in {"нет", "не отправлять"}:
            return (
                state,
                "Заявка не отправлена. Уточните данные или напишите «отмена».",
                True,
            )
        correction = re.match(
            r"(проблема|окружение|влияние|проверки)\s*:\s*(\S.*)", content, re.I | re.S
        )
        if correction:
            field = {
                "проблема": "problem",
                "окружение": "environment",
                "влияние": "impact",
                "проверки": "attempts",
            }[correction[1].casefold()]
            state[field] = correction[2].strip()
            if field == "problem":
                state.pop("check_result", None)
                for key in ("sources", "hypotheses", "unknowns", "_checked_quotes"):
                    state.pop(key, None)
                state["_phase"] = "collect"
        else:
            state["additional_context"] = (
                state.get("additional_context", "") + "\n" + content
            ).strip()
            return state, summary(state), True
    else:
        pending = state.pop("_pending", None)
        if not pending:
            pending = next(
                (field for field in PROMPTS if not state.get(field)),
                "additional_context",
            )
        if normalized in {"да", "нет", "ок", "ага", "привет", "помоги"} and pending in {
            "problem",
            "environment",
            "impact",
        }:
            state["_pending"] = pending
            state["_phase"] = "collect"
            return state, "Нужны детали. " + PROMPTS[pending], False
        state[pending] = (
            (state.get(pending, "") + "\n" + content).strip()[-4000:]
            if pending == "additional_context"
            else content
        )
        patterns = {
            "environment": r"касс[аеы]?\s*№?\s*\d+|магазин\s*№?\s*\d+|верси[яи]\s*\d|windows\s*\d",
            "impact": r"с утра|сегодня|вчера|все кассы|одна касса|работа останов|\d+\s*(?:минут|час)",
            "attempts": r"провер[ия]л|перезагру|перезапус|пробовал|ничего не (?:делал|проверял)",
        }
        for field, pattern in patterns.items():
            if not state.get(field) and re.search(pattern, normalized):
                state[field] = content
    for field in PROMPTS:
        if not state.get(field):
            state["_pending"] = field
            state["_phase"] = "collect"
            return state, PROMPTS[field], False
    problem = state["problem"].casefold().replace("ё", "е")
    for category, pattern, prompt in BRANCHES:
        if re.search(pattern, problem):
            state["_category"] = category
            if not state.get("check_result"):
                state["_pending"] = "check_result"
                state["_phase"] = "check"
                return state, prompt, False
            break
    state["_phase"] = "confirm"
    state.pop("_pending", None)
    return state, summary(state), True
