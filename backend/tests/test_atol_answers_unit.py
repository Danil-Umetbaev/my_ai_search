import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from src.services import atol_answer_router, atol_support_tree as tree
from src.services.atol_semantic_router import advance
from atol_turns import confirm_answer


class PaperAnswerTests(unittest.IsolatedAsyncioTestCase):
    def paper(self):
        state = tree.initial_state()
        for label in ("АТОЛ FPrint-22ПТК", "Бумага и печать", "Красная лампочка и «Нет бумаги»"):
            state, _ = tree.advance(state, label)
        return state

    def llm(self, node, index):
        return SimpleNamespace(route_support=Mock(return_value=json.dumps({"question": node, "choice": index})))

    async def test_free_text_and_buttons_produce_same_instructions_and_facts(self):
        for width in (0, 1):
            for layout in (0, 1):
                state = self.paper()
                buttons = deepcopy(state)
                for text, node, index in (
                    ("Бамаги не осталось", "paper", 0),
                    ("Восемь сантиметров" if width == 0 else "Пять и восемь сантиметра", "width", width),
                    ("Лежит горизонтально" if layout == 0 else "Установлена вертикально", "layout80" if width == 0 else "layout58", layout),
                ):
                    label = tree.catalog()["nodes"][node]["choices"][index]["label"]
                    buttons, expected = tree.advance(buttons, label)
                    state, answer = await confirm_answer(self, state, text, self.llm(node, index))
                    self.assertEqual(answer, expected)
                    self.assertEqual(state["paper_facts"], buttons["paper_facts"])
                    self.assertEqual(state["_atol_tree"]["node"], buttons["_atol_tree"]["node"])
                    self.assertEqual(state["observations"][-1]["answer"], text)

    async def test_correction_invalidates_dependent_conditions(self):
        state = self.paper()
        for label in ("Бумага закончилась", "80 мм", "Горизонтально"):
            state, _ = tree.advance(state, label)
        original = deepcopy(state)
        corrected, answer = await confirm_answer(self, state, "Ошибся: лента 58, а не 80", self.llm("width", 1))
        self.assertEqual(state, original)
        self.assertEqual(corrected["_atol_tree"]["node"], "layout58")
        self.assertEqual(corrected["paper_facts"]["Ширина ленты"], "58 мм")
        self.assertNotIn("Положение кассы", corrected["paper_facts"])
        self.assertIn("Положение кассы", corrected["fact_changes"][-1]["invalidated"])
        self.assertGreater(corrected["_atol_tree"]["revision"], state["_atol_tree"]["revision"])
        self.assertNotIn("1.", answer)

    async def test_presence_can_be_corrected_from_sensor(self):
        state, _ = tree.advance(self.paper(), "Рулон установлен, но ошибка остаётся")
        corrected, _ = await confirm_answer(self, state, "А нет, ошибся, бумага закончилась", self.llm("paper", 0))
        self.assertEqual(corrected["_atol_tree"]["node"], "width")
        self.assertEqual(corrected["paper_facts"]["Наличие рулона"], "Бумага закончилась")

    async def test_repeating_known_condition_does_not_reset_later_answers(self):
        state = self.paper()
        for label in ("Бумага закончилась", "80 мм", "Горизонтально"):
            state, _ = tree.advance(state, label)
        updated, _ = await advance(state, "Бумага закончилась", [], self.llm("paper", 0))
        self.assertEqual(updated["_atol_tree"], state["_atol_tree"])
        self.assertEqual(updated["paper_facts"], state["paper_facts"])

    async def test_unknown_is_not_absent(self):
        state, _ = await confirm_answer(self, self.paper(), "Не могу разглядеть рулон", self.llm("paper", 2))
        self.assertIsNone(state["paper_facts"]["Наличие рулона"])
        self.assertEqual(state["_phase"], "confirm")
        self.assertNotIn("Ширина ленты", state["paper_facts"])

    async def test_ambiguous_and_invalid_answers_do_not_advance(self):
        for raw in ('{"question":null,"choice":null}', '{"question":"resolved","choice":0}',
                    '{"question":"width","choice":0}', '{"question":"paper","choice":true}',
                    '{"question":"paper","choice":-1}', '{"question":"paper","choice":7}', 'broken'):
            state = self.paper()
            llm = SimpleNamespace(route_support=Mock(return_value=raw))
            updated, _ = await advance(state, "Объясните ещё", [], llm)
            self.assertEqual(updated["_atol_tree"], state["_atol_tree"])
            self.assertNotIn("paper_facts", updated)

    async def test_outcomes_are_not_confused_with_conditions(self):
        for text, index, expected in (("Все заработало", 0, "resolved"), ("Сделал, все равно не печатает", 1, "paper_failed"), ("Не смог открыть крышку", 2, "handoff")):
            state = self.paper()
            for label in ("Бумага закончилась", "80 мм", "Горизонтально"):
                state, _ = tree.advance(state, label)
            updated, _ = await confirm_answer(self, state, text, self.llm("paper80h", index))
            self.assertEqual(updated["_atol_tree"]["node"], expected)
            self.assertEqual(updated["paper_facts"], state["paper_facts"])
            self.assertEqual(len(updated["performed_checks"]), 1)

    async def test_buttons_do_not_need_model_and_facts_survive_reload(self):
        state = self.paper()
        llm = SimpleNamespace(route_support=Mock(side_effect=AssertionError("Unexpected model call")))
        for label in ("Бумага закончилась", "58 мм", "Вертикально", "Как выставить ширину 58 мм", "Не помогло"):
            state, _ = await advance(state, label, [], llm, button=True)
            state = json.loads(json.dumps(state))
        self.assertEqual(state["_atol_tree"]["node"], "paper_failed")
        llm.route_support.assert_not_called()

    async def test_model_cannot_invent_sizes_orientation_or_outcomes(self):
        cases = [
            (("Бумага закончилась",), "Обычная", "width", 1),
            (("Бумага закончилась",), "Широкая", "width", 0),
            (("Бумага закончилась",), "Нет", "width", 1),
            (("Бумага закончилась", "80 мм"), "Стоит на столе", "layout80", 2),
            (("Бумага закончилась", "80 мм", "Горизонтально"), "Еще не пробовал", "paper80h", 1),
            (("Бумага закончилась", "80 мм", "Горизонтально"), "Не знаю, помогло ли", "paper80h", 2),
            ((), "На экране написано Нет бумаги", "paper", 0),
            ((), "Вроде есть, а может и нет", "paper", 2),
        ]
        for labels, message, node, choice in cases:
            state = self.paper()
            for label in labels:
                state, _ = tree.advance(state, label)
            updated, _ = await advance(state, message, [], self.llm(node, choice))
            self.assertEqual(updated["_atol_tree"], state["_atol_tree"], message)
            self.assertEqual(updated.get("paper_facts"), state.get("paper_facts"), message)

    async def test_known_error_after_filling_does_not_change_roll_presence(self):
        state = self.paper()
        for label in ("Бумага закончилась", "80 мм", "Горизонтально", "Не помогло"):
            state, _ = tree.advance(state, label)
        updated, _ = await confirm_answer(self, state, "Она опять пишет что нет бумаги", None)
        self.assertEqual(updated["_atol_tree"]["node"], "sensor")
        self.assertEqual(updated["paper_facts"]["Сообщение после заправки"], "Нет бумаги")
        self.assertEqual(updated["paper_facts"]["Наличие рулона"], state["paper_facts"]["Наличие рулона"])


if __name__ == "__main__":
    unittest.main()
