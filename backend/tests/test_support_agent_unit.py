import json
import asyncio
import threading
import unittest

from src.services.support_agent import respond


class FakeLLM:
    def __init__(self, plan):
        self.plan = plan

    def plan_support(self, system, payload):
        self.payload = json.loads(payload)
        return json.dumps(self.plan, ensure_ascii=False)


class SupportAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_drives_question_and_facts_persist(self):
        llm = FakeLLM(
            {
                "action": "ask",
                "question": "На соседней кассе такая же ошибка?",
                "facts": {"problem": "нет связи"},
                "hypotheses": ["сбой сети"],
                "unknowns": ["масштаб"],
            }
        )
        original = {"environment": "касса 3", "_phase": "diagnosing"}
        state, answer = await respond(
            original, [{"role": "user", "content": "касса 3"}], "нет связи", llm
        )
        self.assertEqual(state["environment"], "касса 3")
        self.assertEqual(state["_engine"], "llm")
        self.assertIn("соседней", answer)
        self.assertNotIn("problem", original)
        self.assertEqual(llm.payload["history"][0]["content"], "касса 3")

    async def test_checks_are_exact_document_quotes(self):
        quote = "Проверьте наличие бумаги в принтере."
        llm = FakeLLM({"action": "check", "citations": [{"index": 0, "quote": quote}]})

        async def retrieve(query):
            return [
                {"title": "Печать", "url": "https://example.org/doc", "content": quote}
            ]

        state, answer = await respond({}, [], "Нет чека", llm, retrieve)
        self.assertIn(quote, answer)
        self.assertIn("https://example.org/doc", answer)
        self.assertEqual(len(state["sources"]), 1)

    async def test_fabricated_quote_falls_back(self):
        llm = FakeLLM(
            {
                "action": "check",
                "citations": [
                    {"index": 9, "quote": "Удалите все данные кассы немедленно."}
                ],
            }
        )
        state, answer = await respond({}, [], "Ошибка печати", llm)
        self.assertNotIn("Удалите", answer)
        self.assertIn("временно недоступна", answer)

    async def test_unavailable_model_preserves_dialogue(self):
        state, answer = await respond({}, [], "Ошибка печати")
        self.assertEqual(state["problem"], "Ошибка печати")
        self.assertIn("резервным", answer)

    async def test_escalation_requires_confirmation(self):
        state, answer = await respond(
            {}, [], "Нужен специалист", FakeLLM({"action": "escalate"})
        )
        self.assertEqual(state["_phase"], "confirm")
        self.assertIn("Отправить", answer)
        self.assertNotIn("зарегистрирована", answer)

    async def test_resolution_requires_user_confirmation(self):
        state, answer = await respond(
            {}, [], "Кажется заработало", FakeLLM({"action": "resolved"})
        )
        self.assertEqual(state["_phase"], "verify_resolution")
        self.assertIn("проблема решена", answer)

    async def test_repeated_question_uses_fallback(self):
        question = "Какой текст ошибки?"
        state, answer = await respond(
            {},
            [{"role": "assistant", "content": question}],
            "Нет текста",
            FakeLLM({"action": "ask", "question": question}),
        )
        self.assertNotEqual(answer, question)

    async def test_cancel_does_not_invoke_model(self):
        state, answer = await respond({}, [], "отмена", FakeLLM({"action": "escalate"}))
        self.assertEqual(state["_phase"], "cancelled")

    async def test_model_cannot_invent_user_facts(self):
        llm = FakeLLM(
            {
                "action": "ask",
                "question": "Когда началось?",
                "facts": {"environment": "магазин 999"},
            }
        )
        state, answer = await respond({}, [], "Не печатает чек", llm)
        self.assertNotEqual(state.get("environment"), "магазин 999")
        self.assertIn("резервным", answer)

    async def test_fallback_never_replaces_original_problem(self):
        original = {
            "problem": "Нет чека",
            "environment": "касса 2",
            "impact": "утром",
            "attempts": "перезапуск",
            "check_result": "горит красный",
            "_phase": "diagnosing",
        }
        state, _ = await respond(original, [], "Теперь горит зелёный")
        self.assertEqual(state["problem"], original["problem"])
        self.assertEqual(state["additional_context"], "Теперь горит зелёный")

    async def test_explicit_escalation_without_model(self):
        state, answer = await respond({"problem": "Ошибка"}, [], "передать специалисту")
        self.assertEqual(state["_phase"], "confirm")
        self.assertIn("Отправить", answer)

    async def test_explicit_resolution_without_model(self):
        state, _ = await respond(
            {"problem": "Ошибка", "_phase": "verify_resolution"}, [], "проблема решена"
        )
        self.assertEqual(state["_phase"], "resolved")
        after, _ = await respond(state, [], "да")
        self.assertEqual(after["_phase"], "resolved")

    async def test_changed_fact_keeps_previous_value(self):
        llm = FakeLLM(
            {
                "action": "ask",
                "question": "Что показывает экран?",
                "facts": {"environment": "касса 3"},
            }
        )
        state, _ = await respond(
            {"environment": "касса 2"}, [], "На самом деле касса 3", llm
        )
        self.assertEqual(state["fact_changes"][0]["previous"], "касса 2")

    async def test_repeat_check_is_rejected(self):
        quote = "Проверьте наличие бумаги в принтере."

        async def retrieve(query):
            return [
                {"title": "Печать", "url": "https://example.org/doc", "content": quote}
            ]

        llm = FakeLLM({"action": "check", "citations": [{"index": 0, "quote": quote}]})
        state, answer = await respond(
            {"problem": "Нет чека", "_checked_quotes": [quote]},
            [],
            "Бумага есть",
            llm,
            retrieve,
        )
        self.assertIn("резервным", answer)

    async def test_malformed_json_uses_fallback(self):
        class InvalidLLM:
            def plan_support(self, system, payload):
                return "создал заявку за вас"

        state, answer = await respond({}, [], "Ошибка приложения", InvalidLLM())
        self.assertEqual(state["_engine"], "rules")
        self.assertNotIn("создал", answer)

    async def test_timeout_returns_fallback_without_parallel_gpu_call(self):
        release = threading.Event()
        finished = threading.Event()

        class SlowLLM:
            def plan_support(self, system, payload):
                try:
                    release.wait(2)
                    return '{"action":"escalate"}'
                finally:
                    finished.set()

        try:
            state, answer = await respond(
                {}, [], "Ошибка приложения", SlowLLM(), timeout=0.01
            )
            self.assertEqual(state["_engine"], "rules")
            self.assertFalse(finished.is_set())
        finally:
            release.set()
            await asyncio.to_thread(finished.wait, 2)
            await asyncio.sleep(0.02)

    async def test_retrieval_failure_does_not_lose_message(self):
        async def retrieve(query):
            raise RuntimeError("Search unavailable")

        state, answer = await respond(
            {}, [], "Ошибка приложения", FakeLLM({"action": "escalate"}), retrieve
        )
        self.assertEqual(state["problem"], "Ошибка приложения")

    async def test_cancelled_dialogue_cannot_be_reopened_by_confirmation(self):
        state, _ = await respond({"_phase": "cancelled"}, [], "проблема решена")
        self.assertEqual(state["_phase"], "cancelled")
