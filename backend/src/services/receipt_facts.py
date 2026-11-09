"""Collect explicit observations without choosing a diagnosis or an instruction."""

import re
from dataclasses import dataclass

ALIASES = {"paper": "paper_present", "error": "exact_error", "width": "paper_width_mm"}
DEVICE_SETTINGS = {
    "print_disabled",
    "platform",
    "layout",
    "paper_width_mm",
    "driver_width_mm",
    "paper_compatible",
    "axle_available",
    "limiter_available",
    "fito_connected",
    "connection_type",
    "device_identified",
    "services_stopped_or_absent",
    "mechanism_replaced",
}
SELECTION_FACTS = DEVICE_SETTINGS | {
    "printing_stopped",
    "model",
    "symptom",
    "paper_present",
    "exact_error",
    "paper_indicator",
    "cover_accessible",
    "jam_accessible",
    "fito_installed",
    "os",
    "cash_app_closed",
    "viki_client_available",
    "dreamkas_agent_available",
}
UNKNOWN = r"не знаю|неизвест\w*|не могу (?:прочитать|посмотреть|проверить|определить|понять)|не разобрать|не понимаю|не удалось (?:прочитать|определить|посмотреть|проверить)"
CORRECTION = r"поправлю|исправляю|ошибся|ошиблась|ошиблись|перепут\w*|уточняю|проверил.{0,30}лично|оказалось|на самом деле|все-таки"
MODEL_PATTERNS = (
    (
        r"(?:атол\s*)?(?:fprint|фпринт)[ -]*22\s*птк\b|атол\s*[- ]?22\s*птк\b",
        "АТОЛ FPrint-22ПТК",
    ),
    (r"пирит\s*2\s*[фf]\b", "Пирит 2Ф"),
    (
        r"(?:вики\s*принт|viki\s*print)(?:\s*(57|80)(?:\s*(плюс|plus))?(?:\s*ф\b)?)?",
        "Вики Принт",
    ),
)
SYMPTOMS = (
    (
        "qr_missing",
        r"(?:нет|не печат\w*|пропал\w*|отсутств\w*)[^,.;]{0,20}(?:qr|куар)|(?:qr|куар)[^,.;]{0,20}(?:нет|не печат\w*|пропал\w*)",
    ),
    (
        "blank_print",
        r"(?:пуст\w*|бел\w*) (?:чек|бумаг\w*|лент\w*)|(?:чек|лент\w*|бумаг\w*).{0,25}(?:совершенно пуст\w*|совершенно бел\w*|без текста|вся белая)|ни одной точки",
    ),
    ("pale_print", r"бледн\w*|еле видн\w*"),
    ("partial_print", r"часть строки не пропечат\w*|пропуски|не все точки"),
    ("paper_jam", r"замят\w*|замял\w*|застрял\w*|заклини\w*"),
    ("paper_skew", r"перекос\w*"),
    (
        "no_paper_output",
        r"(?:бумаг\w*|лент\w*).{0,15}не (?:выход\w*|движ\w*)|совсем не выходит|не печат\w* (?:чек|из кассовой)|чек не печат\w*",
    ),
    ("device_error", r"появляется сообщение об ошибке"),
)
BOOLEAN_RULES = {
    "print_disabled": (
        r"(?:запрет печати|галочка|параметр).{0,15}(?:включен\w*|установлен\w*|стоит)",
        r"(?:запрет печати|галочка|параметр).{0,15}(?:выключен\w*|снят\w*|не стоит)",
    ),
    "printing_stopped": (
        r"печать.{0,12}(?:остановлена|завершена)|задания закончены",
        r"печать.{0,12}(?:еще идет|не остановлена)",
    ),
    "cover_accessible": (
        r"крышка.{0,25}открывается|открыл (?:крышку|отсек)",
        r"крышка не открывается|крышку.{0,20}нельзя (?:открыть|поднять)",
    ),
    "paper_compatible": (
        r"подходящ\w*.{0,45}(?:рулон|термобумаг\w*).{0,5}есть",
        r"подходящего рулона нет",
    ),
    "axle_available": (r"ось.{0,40}есть", r"оси.{0,20}нет|стержень.{0,35}потерял\w*"),
    "limiter_available": (r"ограничитель.{0,35}есть", r"ограничителя.{0,20}нет"),
    "jam_accessible": (
        r"(?:смятые кусочки|бумага).{0,25}доступн\w*.{0,40}без разборки",
        r"без разборки не достать|без разбора.{0,15}не дотянуться",
    ),
    "fito_connected": (
        r"fito.{0,18}(?:связалась|подключилась)|fito.{0,10}связь есть|связь fito есть",
        r"fito.{0,20}не (?:соединяется|подключается)|связь не устанавливается",
    ),
    "fito_installed": (
        r"fito.{0,10}установлена",
        r"fito.{0,20}нет|fito не установлена",
    ),
    "cash_app_closed": (
        r"кассовая программа закрыта",
        r"кассовая программа открыта|кассовая программа не закрыта",
    ),
    "device_identified": (
        r"нужную кассу.{0,50}определил по.{0,8}номеру",
        r"не могу понять, какое из устройств",
    ),
    "viki_client_available": (
        r"vikiclient открывается",
        r"vikiclient недоступен|vikiclient.{0,15}не открывается",
    ),
    "dreamkas_agent_available": (
        r"дримкас агент доступен",
        r"дримкас агент недоступен|значка агента нет",
    ),
    "services_stopped_or_absent": (
        r"viki driver и comproxy не установлены или не запущены",
        r"служба viki driver.{0,10}работает|viki driver все-таки работает",
    ),
    "mechanism_replaced": (
        r"механизм.{0,15}заменили|механизм заменен",
        r"механизм не меняли",
    ),
}


def normalize(message):
    text = message.casefold().replace("ё", "е")
    for pattern, replacement in (
        (r"бамаг", "бумаг"),
        (r"пичат", "печат"),
        (r"руллон", "рулон"),
        (r"памагите", "помогите"),
        (r"горизант", "горизонт"),
        (r"вертек", "вертик"),
    ):
        text = re.sub(pattern, replacement, text)
    return text


def observations_only(text):
    patterns = (
        r"\b(?:если|допустим|предположим)\b[^.!?;\n]*",
        r"\b(?:бумага есть|бумаги нет|рулон установлен|рулон есть)\s*\?",
        r"\b(?:у коллеги|у соседа|на соседней кассе|в инструкции написано)[^.!?;\n]*",
    )
    for pattern in patterns:
        text = re.sub(pattern, lambda match: " " * len(match[0]), text)
    return text


def negated(text, start):
    return bool(re.search(r"\bне\s*$", text[max(0, start - 5) : start]))


def model_candidates(text):
    found = []
    for pattern, name in MODEL_PATTERNS:
        for match in re.finditer(pattern, text):
            if negated(text, match.start()):
                continue
            value = name
            if name == "Вики Принт" and match[1]:
                value += " " + match[1]
                if match[2]:
                    value += " Плюс"
                if re.search(r"ф\b", match[0]):
                    value += " Ф"
            found.append((match.start(), value))
    return found


def split_device_error(message):
    """Mask only a reported message, not the physical observation next to it."""
    pattern = r'(?:пишет|написано на экране|сообщение на экране|ошибка на экране|текст ошибки|на экране|ошибка:)\s*[:—-]?\s*(?:[«"“]([^»"”]+)[»"”]|([^.;\n]+))'
    spans = []
    errors = []
    for match in re.finditer(pattern, message, re.I):
        value = match[1] or match[2]
        value = re.split(
            r",?\s+(?:хотя|но рулон|а рулон|при этом рулон)\s+|,\s*(?=рулон|бумага есть)",
            value,
            maxsplit=1,
            flags=re.I,
        )[0]
        start = match.start(1) if match[1] is not None else match.start(2)
        spans.append((start, start + len(value)))
        errors.append(value.strip())
    masked = message
    for start, end in reversed(spans):
        masked = masked[:start] + " " * (end - start) + masked[end:]
    return masked, errors


def check_result(message):
    text = normalize(message).strip(" .!?")
    if re.search(r"не (?:смог|могу|удалось) выполн", text):
        return {"problem_resolved": None, "procedure_completed": False}
    if (
        re.search(r"не помог|проблема (?:та же|осталась)|по-прежнему не печат", text)
        or text == "нет"
    ):
        return {"problem_resolved": False}
    if message.rstrip().endswith("?") or re.search(r"не уверен|не знаю|не думаю", text):
        return {}
    if text in {
        "да",
        "помогло",
        "да, помогло",
        "печатает",
        "заработало",
        "все работает",
    } or re.search(
        r"(?:теперь|снова|обычный) чек (?:снова )?печатается|проблема (?:исчезла|решена)|чек напечатался нормально",
        text,
    ):
        return {"problem_resolved": True}
    return {}


def legacy_facts(flow):
    facts = flow.setdefault("facts", {})
    for key in ("model", "layout"):
        if key not in facts and flow.get(key):
            facts[key] = flow[key]
    if "paper_present" not in facts and flow.get("paper") in {"present", "absent"}:
        facts["paper_present"] = flow["paper"] == "present"
    if "paper_width_mm" not in facts and flow.get("width") in {"58", "80"}:
        facts["paper_width_mm"] = int(flow["width"])
    if "exact_error" not in facts and flow.get("error"):
        text = normalize(flow["error"])
        facts["exact_error"] = (
            None if re.search(UNKNOWN + r"|ошибки нет", text) else flow["error"]
        )
        facts["error_status"] = (
            "absent"
            if "ошибки нет" in text
            else "unknown" if facts["exact_error"] is None else "reported"
        )
    if "symptom" not in facts and flow.get("symptom"):
        for value, pattern in SYMPTOMS:
            if re.search(pattern, normalize(flow["symptom"])):
                facts["symptom"] = value
                break
    return facts


@dataclass
class FactUpdate:
    changed: set[str]
    invalidated: set[str]
    conflicts: set[str]


def extract_candidates(message, field):
    masked, errors = split_device_error(message)
    text = observations_only(normalize(masked))
    original = normalize(message)
    candidates = {}

    def add(key, value, position=0):
        candidates.setdefault(key, []).append((position, value))

    for position, value in model_candidates(text):
        add("model", value, position)
    if re.search(r"неизвестн\w* (?:другая )?модель|модель.{0,12}неизвестн", text):
        candidates["model"] = [(0, None)]
    if re.search(r"другая платформа", text):
        add("platform", None)
    for key, (yes, no) in BOOLEAN_RULES.items():
        if key == "print_disabled" and field != key and "запрет печати" not in text:
            continue
        negative_spans = [m.span() for m in re.finditer(no, text)]
        for pattern, value in ((no, False), (yes, True)):
            for match in re.finditer(pattern, text):
                if value and (
                    negated(text, match.start())
                    or any(
                        start < match.end() and end > match.start()
                        for start, end in negative_spans
                    )
                ):
                    continue
                add(key, value, match.start())
    paper_patterns = (
        (
            False,
            r"\bбумаг\w*(?:\s+(?:в отсеке|в кассе|совсем|вообще|больше|полностью|физически|у меня))*\s+(?:нет|закончилась|кончилась)|нет бумаг\w*|\bрулона(?:\s+в отсеке)?\s+нет",
        ),
        (
            True,
            r"\bбумаг\w* (?:физически )?есть|\bрулон (?:физически )?(?:установлен|есть|стоит)|полный рулон|\bрулон.{0,8}вижу",
        ),
    )
    for value, pattern in paper_patterns:
        for match in re.finditer(pattern, text):
            if re.search(
                r"запасн\w*\s*$", text[max(0, match.start() - 20) : match.start()]
            ) or re.match(r"\s+(?:на полке|в запасе|на складе)", text[match.end() :]):
                continue
            if re.search(
                r"подходящ\w*\s*$", text[max(0, match.start() - 20) : match.start()]
            ) and not re.search(r"установлен|стоит", match[0]):
                continue
            if not negated(text, match.start()) and not re.search(
                r"не (?:закончилась|кончилась)", match[0]
            ):
                add("paper_present", value, match.start())
    for value, pattern in SYMPTOMS:
        for match in re.finditer(pattern, text):
            if not negated(text, match.start()) and not re.match(
                r"\s+нет\b", text[match.end() :]
            ):
                add("symptom", value, match.start())
    # A specific symptom refines the generic "not printing" observation.
    symptoms = candidates.get("symptom", [])
    if len({v for _, v in symptoms}) > 1:
        candidates["symptom"] = [
            (p, v)
            for p, v in symptoms
            if v != "no_paper_output"
            or not re.match(r"(?:не печат|чек не печат)", text[p:])
        ]
    if {v for _, v in candidates.get("symptom", [])} == {"pale_print", "partial_print"}:
        candidates["symptoms"] = [(0, "pale_print,partial_print")]
        candidates["symptom"] = [max(candidates["symptom"], key=lambda item: item[0])]
    for key, pattern, convert in (
        ("platform", r"платформа\s+(\d+(?:\.\d+)*)", str),
        ("os", r"\b(windows|linux)\b", lambda v: v.title()),
        (
            "layout",
            r"\b(горизонт\w*|вертик\w*)",
            lambda v: "horizontal" if v.startswith("горизонт") else "vertical",
        ),
        (
            "paper_indicator",
            r"индикатор бумаг\w*.{0,10}(красн\w*|зелен\w*)",
            lambda v: "red" if v.startswith("красн") else "green",
        ),
        (
            "connection_type",
            r"тип подключения\s*[-—:]?\s*(viki driver|comproxy|напрямую через com)",
            lambda v: {
                "viki driver": "viki_driver",
                "comproxy": "comproxy",
                "напрямую через com": "direct_com",
            }[v],
        ),
        (
            "operation",
            r"ошибка при\s+(регистрации|закрытии архива фн|закрытии смены|продаже)",
            lambda v: {
                "регистрации": "registration",
                "закрытии архива фн": "close_fn_archive",
                "закрытии смены": "shift_close",
                "продаже": "sale",
            }[v],
        ),
    ):
        for match in re.finditer(pattern, text):
            if not negated(text, match.start()):
                add(key, convert(match[1]), match.start())
    for clause in re.split(r"[.!;\n]", text):
        widths = list(re.finditer(r"\b(57|58|80)\s*мм\b", clause))
        if not widths:
            continue
        target = (
            "driver_width_mm"
            if "драйвер" in clause and not re.search(r"упаков|пачк", clause)
            else "paper_width_mm"
        )
        if re.search(r"не знаю|не проверял", clause) and "драйвер" in clause:
            add("driver_width_mm", None)
        if (
            target == "paper_width_mm"
            and not re.search(r"лент|бумаг|упаков|пачк|ширин", clause)
            and field != target
        ):
            continue
        for match in widths:
            if not negated(clause, match.start()):
                add(target, int(match[1]), text.find(clause) + match.start())
    if errors and not re.search(
        UNKNOWN + r"|прочитать.{0,8}не могу", normalize(errors[-1])
    ):
        add("exact_error", errors[-1])
        add("error_status", "reported")
    if re.search(r"ошибки нет|ошибок нет", original):
        add("exact_error", None)
        add("error_status", "absent")
    unreadable = re.search(
        r"не могу прочитать|прочитать.{0,8}не могу|не разобрать", original
    )
    if unreadable and (
        field == "exact_error" or re.search(r"ошибк\w*|сообщени\w*|\bкод\b", original)
    ):
        add("exact_error", None)
        add("error_status", "unknown")
    short = text.strip(' .!?«»"')
    if field == "platform" and re.fullmatch(r"\d+(?:\.\d+)+", short):
        add(field, short)
    if field == "connection_type":
        value = {
            "viki driver": "viki_driver",
            "comproxy": "comproxy",
            "напрямую через com": "direct_com",
            "com": "direct_com",
        }.get(short)
        if value:
            add(field, value)
    if field == "paper_indicator":
        if re.fullmatch(r"(?:горит )?красн\w*", short):
            add(field, "red")
        elif re.fullmatch(r"(?:горит )?зелен\w*", short):
            add(field, "green")
        elif short == "не горит":
            add(field, "off")
    if field == "exact_error" and not errors and not candidates.get("error_status"):
        if short in {"нет", "нет ошибки"}:
            add("exact_error", None)
            add("error_status", "absent")
        elif re.search(UNKNOWN, text):
            add("exact_error", None)
            add("error_status", "unknown")
        elif "введу текст" not in text and not candidates and message.strip():
            add("exact_error", message.strip())
            add("error_status", "reported")
    elif field in BOOLEAN_RULES or field == "paper_present":
        if short in {"да", "есть", "ага"}:
            add(field, True)
        elif short == "нет":
            add(field, False)
    if field in {"paper_width_mm", "driver_width_mm"} and re.fullmatch(
        r"(?:57|58|80)(?:\s*мм)?", short
    ):
        add(field, int(re.search(r"\d+", short)[0]))
    unknown_current = re.search(UNKNOWN, short) and (
        not candidates
        or re.match(
            r"(?:этого |точно |сейчас )?(?:не знаю|не могу проверить|не могу прочитать)",
            short,
        )
    )
    if field in SELECTION_FACTS and field not in candidates and unknown_current:
        candidates[field] = [(0, None)]
        if field == "exact_error":
            candidates["error_status"] = [(0, "unknown")]
    if re.search(r"модель не знаю|модель.{0,8}неизвестна", text):
        candidates["model"] = [(0, None)]
    for key, pattern in (
        ("paper_present", r"не могу определить.{0,25}(?:бумаг|рулон)"),
        (
            "fito_connected",
            r"не понимаю.{0,25}(?:связь|подключ)|не знаю.{0,25}(?:связь|подключ)",
        ),
        (
            "driver_width_mm",
            r"настройку драйвера не проверял|ширин\w* в драйвере не знаю",
        ),
    ):
        if re.search(pattern, text):
            candidates[key] = [(0, None)]
    if candidates.get("model") and re.search(
        r"вроде|кажется|не уверен|не знаю,? чему верить", text
    ):
        candidates["model"].append((len(text), None))
    return candidates


def collect_facts(flow, message, pending=None, selected_fact=None):
    facts = legacy_facts(flow)
    before = dict(facts)
    field = ALIASES.get(pending, pending)
    candidates = extract_candidates(message, field)
    if selected_fact is not None:
        if selected_fact["field"] != field or field == "allowed_operator":
            raise ValueError("Choice does not belong to the current fact question")
        candidates[field] = [(0, selected_fact["value"])]
    text = normalize(message)
    correction_positions = [
        match.end()
        for match in re.finditer(CORRECTION + r"|\bтеперь\b|на самом деле", text)
    ]
    conflicts = flow.setdefault("fact_conflicts", {})
    resolved = {}
    for key, values in candidates.items():
        unique = list(dict.fromkeys(v for _, v in values))
        if len(unique) == 1:
            resolved[key] = unique[0]
            conflicts.pop(key, None)
        elif correction_positions and not re.search(
            r"не знаю,? (?:что|чему)|не уверен", text
        ):
            current = list(
                dict.fromkeys(
                    value
                    for position, value in values
                    if position >= correction_positions[-1]
                )
            )
            if len(current) == 1:
                resolved[key] = current[0]
                conflicts.pop(key, None)
            else:
                resolved[key] = None
                conflicts[key] = unique
        else:
            resolved[key] = None
            conflicts[key] = unique
    invalidated = set()
    if (
        "model" in resolved
        and before.get("model") is not None
        and before["model"] != resolved["model"]
    ):
        invalidated = DEVICE_SETTINGS - resolved.keys()
        for key in invalidated:
            facts.pop(key, None)
            conflicts.pop(key, None)
    facts.update(resolved)
    if any(before.get(key) != facts.get(key) for key in SELECTION_FACTS):
        facts.pop("problem_resolved", None)
        facts.pop("procedure_completed", None)
    if pending == "result":
        facts.update(check_result(message))
    changed = {
        key
        for key in before.keys() | facts.keys()
        if before.get(key) != facts.get(key) or (key in before) != (key in facts)
    }
    history = flow.setdefault("fact_changes", [])
    for key in sorted(changed):
        history.append(
            {
                "field": key,
                "before": before.get(key),
                "after": facts.get(key),
                "reason": "model_changed" if key in invalidated else "user",
                "text": message,
            }
        )
    flow["fact_changes"] = history[-80:]
    sync_legacy(flow)
    return FactUpdate(changed, invalidated, set(conflicts))


def sync_legacy(flow):
    facts = flow["facts"]
    model = facts.get("model")
    flow["model"] = "Вики Принт" if model and model.startswith("Вики Принт") else model
    flow["layout"] = facts.get("layout")
    flow["width"] = (
        str(facts["paper_width_mm"])
        if facts.get("paper_width_mm") is not None
        else None
    )
    paper = facts.get("paper_present")
    flow["paper"] = "present" if paper is True else "absent" if paper is False else None
    flow["paper_missing"] = paper is False
    flow["error"] = facts.get("exact_error") or {
        "absent": "Ошибки нет",
        "unknown": "Неизвестно",
    }.get(facts.get("error_status"))
    flow["symptom"] = {
        "qr_missing": "не печатается QR-код",
        "blank_print": "выходит пустой чек",
        "no_paper_output": "чек не печатается",
        "pale_print": "бледная печать",
        "partial_print": "частичная печать",
        "paper_jam": "бумага замялась",
        "paper_skew": "перекос бумаги",
        "device_error": "сообщение об ошибке",
    }.get(facts.get("symptom"))
