import unittest
from src.services.diagnosis import advance, is_ready, ticket_details


class DiagnosisTests(unittest.TestCase):
    def test_collects_context_before_confirmation(self):
        state = {}
        for index, answer in enumerate(
            ["Ошибка", "Касса 2", "С утра", "Перезапуск не помог"]
        ):
            previous = dict(state)
            state, prompt, ready = advance(state, answer)
            self.assertEqual(ready, index == 3)
            self.assertTrue(prompt)
            self.assertNotIn(answer, previous.values())
        self.assertEqual(state["attempts"], "Перезапуск не помог")

    def test_skips_facts_in_initial_description(self):
        state, prompt, ready = advance(
            {}, "Касса 2: сегодня ошибка печати чека, перезапуск не помог"
        )
        self.assertFalse(ready)
        self.assertEqual(state["_pending"], "check_result")
        self.assertIn("бумаги", prompt)
        state, prompt, ready = advance(state, "Бумага есть, красный индикатор")
        self.assertTrue(ready)
        self.assertIn("красный индикатор", prompt)
        self.assertNotIn("_phase", ticket_details(state))

    def test_branches_depend_on_problem(self):
        for problem, expected in [
            ("Не проходит оплата", "терминал"),
            ("Нет интернета", "ресурс"),
            ("Не могу войти", "коллег"),
        ]:
            state = {
                "problem": problem,
                "environment": "касса 2",
                "impact": "с утра",
                "attempts": "не проверял",
                "_phase": "collect",
                "_pending": "attempts",
            }
            state, prompt, ready = advance(state, "Ничего не делал")
            self.assertFalse(ready)
            self.assertIn(expected, prompt)

    def test_vague_answer_does_not_fill_environment(self):
        state, _, _ = advance({}, "Ошибка приложения")
        state, prompt, ready = advance(state, "да")
        self.assertNotIn("environment", state)
        self.assertFalse(ready)
        self.assertIn("магазин", prompt)

    def test_correction_restarts_relevant_check(self):
        state = {
            "problem": "Ошибка приложения",
            "environment": "касса 2",
            "impact": "утром",
            "attempts": "ничего",
            "_phase": "confirm",
        }
        updated, prompt, ready = advance(state, "проблема: не проходит оплата")
        self.assertFalse(ready)
        self.assertIn("терминал", prompt)
        self.assertEqual(state["problem"], "Ошибка приложения")
        self.assertFalse(is_ready(updated))

    def test_legacy_session_and_additional_context(self):
        state = {
            "problem": "Ошибка",
            "environment": "касса 2",
            "impact": "утром",
            "attempts": "ничего",
        }
        self.assertTrue(is_ready(state))
        updated, prompt, ready = advance(state, "Также тормозит интерфейс")
        self.assertTrue(ready)
        self.assertEqual(updated["problem"], "Ошибка")
        self.assertIn("Также тормозит", prompt)

    def test_cancel_prevents_confirmation(self):
        state, _, _ = advance({}, "Ошибка приложения")
        state, _, ready = advance(state, "отмена")
        self.assertFalse(ready)
        state, _, _ = advance(state, "да")
        self.assertFalse(is_ready(state))
