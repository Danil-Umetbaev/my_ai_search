import unittest
from src.services.dialogue import DialogueService, support_evidence_allowed


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.service = DialogueService()

    def follow(self, *messages):
        state = {}
        for message in messages:
            decision = self.service.route(message, state)
            state = decision.state
        return decision

    def test_vague_complaint_collects_facts_before_search(self):
        first = self.follow("У меня блять ничего не работает, помоги")
        self.assertEqual(first.action, "clarify")
        self.assertEqual(first.state["pending"], "subject")
        final = self.follow("У меня блять ничего не работает, помоги", "касса", "чёрный экран")
        self.assertEqual(final.action, "search")
        self.assertIn("Чёрный экран", final.query)
        self.assertNotIn("неисправен", final.query)

    def test_specific_symptom_searches_without_mandatory_questionnaire(self):
        result = self.follow("касса не работает", "Черный экран")
        self.assertEqual(result.action, "search")
        self.assertNotIn("device", result.state["facts"])
        self.assertNotIn("indicator", result.state["facts"])

    def test_error_requested_only_after_unsuccessful_search(self):
        result = self.follow("Не печатает чек")
        self.assertEqual(result.action, "search")
        followup = self.service.missing_answer(result.state)
        self.assertEqual(followup.state["pending"], "error_text")
        result = self.service.route("Не могу прочитать", followup.state)
        self.assertEqual(result.action, "search")
        self.assertEqual(result.state["facts"]["error_text"], "Неизвестно")
        self.assertEqual(self.service.missing_answer(result.state).action, "handoff")

    def test_regular_question_bypasses_intake(self):
        self.assertEqual(self.follow("Где находится раздел Карты?").action, "direct")

    def test_independent_question_resets_old_incident(self):
        result = self.follow("касса сломалась", "Как изменить язык интерфейса?")
        self.assertEqual(result.action, "direct")
        self.assertEqual(result.state, {})

    def test_numeric_error_answer_keeps_context(self):
        first = self.follow("не печатает чек")
        pending = self.service.missing_answer(first.state)
        result = self.service.route("123", pending.state)
        self.assertEqual(result.state["facts"]["error_text"], "123")
        self.assertEqual(result.action, "search")

    def test_meaningless_reply_does_not_become_symptom(self):
        result = self.follow("касса сломалась", "фывапролдж")
        self.assertEqual(result.action, "interpret")
        self.assertNotIn("symptom", result.state["facts"])

    def test_user_can_request_human(self):
        self.assertEqual(self.follow("касса сломалась", "позовите специалиста").action, "handoff")

    def test_explicit_restart_discards_old_facts(self):
        result = self.follow("касса сломалась", "чёрный экран", "Новая проблема: не печатает чек")
        self.assertEqual(result.state["facts"]["subject"], "Печать чека")
        self.assertNotEqual(result.state["facts"]["symptom"], "Чёрный экран")

    def test_state_is_not_shared_or_mutated(self):
        original = self.follow("касса сломалась").state
        first = self.service.route("чёрный экран", original)
        second = self.service.route("зависла", original)
        self.assertNotIn("symptom", original["facts"])
        self.assertNotEqual(first.state["facts"], second.state["facts"])

    def test_clarification_has_a_limit(self):
        state = {"initial": "Не работает", "facts": {}, "stage": "collecting", "pending": "subject", "turns": 6}
        self.assertEqual(self.service.route("не знаю", state).action, "handoff")

    def test_failed_solution_is_not_repeated_forever(self):
        state = {"stage": "awaiting_result", "facts": {}, "searches": 2}
        self.assertEqual(self.service.route("не помогло", state).action, "handoff")

    def test_repeated_complaint_does_not_invent_symptoms(self):
        result = self.follow("Не работает касса", "Да просто работать перестала!")
        self.assertEqual(result.action, "clarify")
        self.assertEqual(result.state["pending"], "symptom")
        self.assertNotIn("symptom", result.state["facts"])

    def test_label_printer_is_not_receipt_printer(self):
        result = self.follow("Не печатает ценники")
        self.assertEqual(result.state["facts"]["subject"], "Печать ценников или этикеток")

    def test_changed_symptom_discards_old_observations(self):
        state = self.follow("Касса сломалась", "Черный экран").state
        state.update(stage="collecting", pending="details")
        state["facts"]["indicator"] = "Горит"
        result = self.service.route("Теперь ошибка 123", state)
        self.assertNotIn("indicator", result.state["facts"])
        self.assertEqual(result.state["facts"]["error_text"], "Теперь ошибка 123")

    def test_device_answer_preserves_printing_incident(self):
        state = self.follow("Не печатает чек").state
        state.update(stage="collecting", pending="device")
        result = self.service.route("обычная касса", state)
        self.assertEqual(result.action, "search")
        self.assertEqual(result.state["facts"]["subject"], "Печать чека")
        self.assertEqual(result.state["facts"]["symptom"], "Не печатает чек")

    def test_reference_question_can_interrupt_intake(self):
        result = self.follow("Касса сломалась", "Что находится в разделе Справочники?")
        self.assertEqual(result.action, "direct")
        self.assertEqual(result.state, {})

    def test_question_from_documentation_preserves_original_request(self):
        followup = self.service.ask_from_evidence({}, "На кассе или в интерфейсе сервера?", "Как поменять язык?")
        self.assertEqual(followup.state["mode"], "question")
        self.assertIn("язык", followup.state["initial"])
        repeated = self.service.ask_from_evidence(followup.state, followup.answer, "на сервере")
        self.assertEqual(repeated.action, "handoff")

    def test_table_heading_is_not_a_solution(self):
        self.assertFalse(support_evidence_allowed("Сообщения об ошибках на экране кассира при печати чековых документов", "Ошибка Причина Что делать?", "Не печатает чек"))

    def test_printing_guide_does_not_solve_frozen_screen(self):
        self.assertFalse(support_evidence_allowed("Сообщения об ошибках на экране кассира при печати чековых документов", "Позовите администратора.", "Касса зависла"))

    def test_source_gate_rejects_engineering_instructions(self):
        self.assertFalse(support_evidence_allowed("Настройка PostgreSQL", "Измените конфигурацию базы данных"))
        self.assertFalse(support_evidence_allowed("Касса Руководство пользователя", "Выберите → нажмите клавишу ВВОД"))
        self.assertTrue(support_evidence_allowed("Касса Руководство пользователя", "Позовите администратора магазина."))


class InterpretationTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_cannot_replace_observation_with_another_symptom(self):
        class LLM:
            def interpret_reply(self, message, question, choices):
                return {"kind": "answer", "value": "Не печатает чек", "evidence": "всё встало"}
        service = DialogueService()
        state = service.route("Не работает касса", {}).state
        result = await service.interpret("Там всё встало намертво", state, LLM())
        self.assertEqual(result.state["facts"]["symptom"], "Там всё встало намертво")
        self.assertNotIn("Не печатает чек", service.summary(result.state))


if __name__ == "__main__":
    unittest.main()
