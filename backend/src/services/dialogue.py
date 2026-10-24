import re
from dataclasses import dataclass, field


@dataclass
class DialogueDecision:
    action: str
    state: dict
    answer: str = ""
    choices: list[str] = field(default_factory=list)
    query: str = ""


class DialogueService:
    QUESTIONS = {
        "subject": ("Помогу разобраться. Что именно не работает?", ["Касса", "Печать чека", "Оплата картой", "Другое"]),
        "symptom": ("Что сейчас происходит с кассой?", ["Чёрный экран", "Зависла", "Сообщение об ошибке", "Не печатает чек"]),
        "indicator": ("На мониторе горит индикатор питания — маленькая лампочка возле кнопки включения?", ["Горит", "Не горит", "Не знаю"]),
        "error_text": ("Напишите, пожалуйста, текст или код ошибки так, как он показан на экране. Если сообщения нет — напишите «ошибки нет».", ["Ошибки нет", "Не могу прочитать"]),
        "device": ("Это обычная касса с кассиром или касса самообслуживания?", ["Обычная касса", "Касса самообслуживания", "Не знаю"]),
        "details": ("Что вы пытались сделать и что произошло вместо ожидаемого результата? Можно написать своими словами.", ["Не знаю"]),
    }
    LABELS = {"subject": "Устройство или операция", "symptom": "Симптом", "indicator": "Индикатор монитора", "error_text": "Ошибка на экране", "device": "Тип кассы", "details": "Наблюдения"}

    @staticmethod
    def normalize(text):
        return " ".join(text.casefold().replace("ё", "е").split()).strip(" .!?")

    @classmethod
    def is_incident(cls, text):
        value = cls.normalize(text)
        return bool(re.search(r"не (?:работает|работают|включается|запускается|печатает|проходит)|перестал[аио]? работ|слом|завис|погас|потух|черн[ыо]й экран|ошибк[аиу]|фискализатор|помоги|ничего не", value))

    @staticmethod
    def summary(state):
        lines = ["Обращение: " + state.get("initial", "")]
        for key, value in state.get("facts", {}).items():
            lines.append(f"{DialogueService.LABELS.get(key, key)}: {value}")
        if state.get("failed_answer"):
            lines.append("Предыдущий ответ не помог: " + state["failed_answer"][:600])
        return "\n".join(lines)

    def ask(self, state, field, repeated=False):
        state.pop("question", None)
        state["pending"] = field
        state["stage"] = "collecting"
        state["turns"] = state.get("turns", 0) + 1
        question, choices = self.QUESTIONS[field]
        if field == "symptom" and state.get("facts", {}).get("subject") not in {"Касса", "Печать чека", "Оплата картой"}:
            question = "Что именно происходит: есть сообщение об ошибке, устройство не реагирует или что-то другое?"
            choices = ["Сообщение об ошибке", "Не реагирует", "Другое", "Не знаю"]
        if repeated:
            question = "Понял, проблема пока осталась. " + question
        return DialogueDecision("clarify", state, question, choices)

    def advance(self, state):
        facts = state["facts"]
        if state.get("turns", 0) >= 6:
            state["stage"] = "handoff"
            return DialogueDecision("handoff", state)
        if state.get("mode") == "question":
            state["pending"] = None
            state["stage"] = "searching"
            return DialogueDecision("search", state, query=self.summary(state))
        if not facts.get("subject") or facts.get("subject") == "Неизвестно":
            return self.ask(state, "subject")
        if not facts.get("symptom") and not facts.get("details"):
            return self.ask(state, "symptom")
        state["pending"] = None
        state["stage"] = "searching"
        return DialogueDecision("search", state, query=self.summary(state))

    def missing_answer(self, state):
        state["misses"] = state.get("misses", 0) + 1
        facts = state.get("facts", {})
        if state["misses"] == 1 and state.get("turns", 0) < 6:
            if facts.get("subject") in {"Печать чека", "Оплата картой"} and not facts.get("error_text"):
                return self.ask(state, "error_text")
            if not facts.get("details"):
                return self.ask(state, "details")
        return DialogueDecision("handoff", state)

    def ask_from_evidence(self, state, question, initial):
        if not state:
            state = {"initial": initial, "facts": {}, "mode": "question", "turns": 0}
        if state.get("turns", 0) >= 6 or question == state.get("question"):
            return DialogueDecision("handoff", state)
        state.update(stage="collecting", pending="details", question=question,
                     turns=state.get("turns", 0) + 1)
        return DialogueDecision("clarify", state, question)

    def route(self, message, previous):
        state = {**(previous or {}), "facts": dict((previous or {}).get("facts", {}))}
        text = self.normalize(message)
        if re.search(r"^(?:новая проблема|другая проблема|новый вопрос|другой вопрос|начать заново)", text):
            state = {}
            message = re.sub(r"^(?:новая проблема|другая проблема|новый вопрос|другой вопрос|начать заново)\s*[:.,!-]?\s*", "", message, flags=re.I)
            text = self.normalize(message)
            if not text:
                return self.ask({"initial": "Новое обращение", "facts": {}}, "subject")
        if re.search(r"\b(?:позови|позовите|соедини|соедините|нужен|дайте)\b.*\b(?:оператор|специалист|человек|техподдерж)", text):
            state.setdefault("initial", message)
            state.setdefault("facts", {})
            state["stage"] = "handoff"
            return DialogueDecision("handoff", state)
        if state and text in {"спасибо помогло", "помогло", "заработало", "все работает", "решено"}:
            state["stage"] = "resolved"
            state["pending"] = None
            return DialogueDecision("resolved", state, "Отлично, рад, что получилось. Если возникнет другая проблема — напишите.")
        active = state.get("stage") in {"collecting", "awaiting_result"}
        standalone = bool(re.match(r"(?:как|где|можно ли|какие|какой|что|чем|сколько|для чего|почему)\b", text))
        if active and standalone and not self.is_incident(text):
            return DialogueDecision("direct", {}, query=message)
        if state.get("stage") == "awaiting_result" and re.search(r"не помог|не работает|не получилось|все так же", text):
            if state.get("searches", 0) >= 2:
                state["stage"] = "handoff"
                return DialogueDecision("handoff", state)
            state["failed_answer"] = state.pop("last_answer", "")
            return self.ask(state, "details")
        if not active:
            if not self.is_incident(text):
                return DialogueDecision("direct", {}, query=message)
            state = {"initial": message[:1000], "facts": {}, "turns": 0, "searches": 0}
        facts = state["facts"]
        pending = state.get("pending")
        before = dict(facts)
        if re.search(r"самообслуж|\bксо\b", text):
            facts.setdefault("subject", "Касса")
            facts["device"] = "Касса самообслуживания"
        elif re.search(r"обычн.*касс|касс.*кассир", text):
            facts.setdefault("subject", "Касса")
            facts["device"] = "Обычная касса"
        elif re.search(r"касс", text):
            facts.setdefault("subject", "Касса")
        if re.search(r"ценник|этикетк", text):
            facts["subject"] = "Печать ценников или этикеток"
        elif re.search(r"печат|принтер|фискализатор|фискальн", text):
            facts["subject"] = "Печать чека"
        elif re.search(r"оплат.*карт|карт.*оплат|терминал", text):
            facts["subject"] = "Оплата картой"
        if re.search(r"черн[ыо]й экран|экран черн|(?:экран|монитор).*?(?:погас|потух)|(?:погас|потух).*?(?:экран|монитор)", text):
            facts["symptom"] = "Чёрный экран"
        elif re.search(r"завис|не реагирует", text):
            facts["symptom"] = "Зависает или не реагирует"
        elif re.search(r"не печатает|не выходит чек", text):
            facts["symptom"] = "Не печатает чек"
        elif re.search(r"ошибк", text) and text not in {"ошибки нет", "нет ошибки"}:
            facts["symptom"] = "Сообщение об ошибке"
            if re.search(r"\d", text):
                facts["error_text"] = message[:500]
        unknown = text in {"не знаю", "хз", "не понимаю", "не могу прочитать", "без понятия"}
        if pending == "subject" and text == "другое":
            facts["subject"] = "Другое"
        if pending == "indicator" or re.search(r"индикатор|лампочк", text):
            if unknown:
                facts["indicator"] = "Неизвестно"
            elif re.search(r"не горит|не светит|^нет$", text):
                facts["indicator"] = "Не горит"
            elif re.search(r"горит|светит|^да$", text):
                facts["indicator"] = "Горит"
        elif pending in {"device", "error_text", "details", "symptom", "subject"} and unknown:
            facts[pending] = "Неизвестно"
        elif pending == "error_text" and text in {"ошибки нет", "нет ошибки", "нет"}:
            facts[pending] = "Сообщения об ошибке нет"
        elif pending == "error_text" and re.search(r"\d", text) and len(text) <= 150:
            facts[pending] = message[:500]
        if before.get("subject") and facts.get("subject") != before["subject"]:
            for key in ("symptom", "indicator", "error_text", "device", "details"):
                if facts.get(key) == before.get(key):
                    facts.pop(key, None)
        if before.get("symptom") and facts.get("symptom") != before["symptom"]:
            for key in ("indicator", "error_text", "details"):
                if facts.get(key) == before.get(key):
                    facts.pop(key, None)
        if active and before == facts:
            if state.get("turns", 0) >= 6:
                state["stage"] = "handoff"
                return DialogueDecision("handoff", state)
            if re.search(r"(?:просто|вообще|ничего|все|работать).*(?:не работает|перестал)|(?:не работает|перестал).*работ", text):
                return self.ask(state, pending or "details", repeated=True)
            return DialogueDecision("interpret", state)
        return self.advance(state)


    async def interpret(self, message, state, llm):
        from src.middleware.ai_capacity import run_model
        pending = state.get("pending") or "details"
        question, choices = self.QUESTIONS[pending]
        if state.get("question"):
            question, choices = state["question"], []
        result = await run_model(llm.interpret_reply, message, question, choices)
        if result.get("kind") == "off_topic":
            return DialogueDecision("off_topic", state, "Я помогу с рабочей проблемой. " + question, choices)
        if result.get("kind") == "question" and re.match(r"(?:как|где|можно ли|какие|что|чем|сколько|почему)\b", self.normalize(message)):
            return DialogueDecision("direct", {}, query=message)
        if result.get("kind") == "answer":
            state["facts"][pending] = message[:500]
            return self.advance(state)
        if state.get("question"):
            state["turns"] = state.get("turns", 0) + 1
            return DialogueDecision("clarify", state, question, choices)
        return self.ask(state, pending, repeated=True)


def support_evidence_allowed(title, evidence, question=""):
    employee_guide = bool(re.search(r"(?:касс.*руководство пользователя|сообщения об ошибках на экране кассира)", title, re.I))
    incomplete = bool(re.search(r"(?:нажмите|кликните|выберите|клавиш[ау])\s*(?:[.→]|$)", evidence, re.I))
    technical = bool(re.search(r"\b(?:sql|sudo|ssh|systemctl|postgres|root|select|update|delete)\b|баз[ауы] данных|конфигурационн|реестр|фискализац|замен.*накопител", evidence, re.I))
    actionable = bool(re.search(r"\b(?:позовите|вызовите|обратитесь|остановите|нажмите|выберите|проверьте|введите|откройте|закройте)\b", evidence, re.I))
    if "печати чековых" in title.casefold() and not re.search(r"печат|чеков.*принтер|фискал", question, re.I):
        return False
    return employee_guide and actionable and not incomplete and not technical
