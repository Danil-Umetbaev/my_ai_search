import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from src.services import atol_support_tree as tree
from src.services.atol_semantic_router import advance
from src.services.atol_answer_state import configuration
from src.services.atol_answer_router import parse_answer, questions


class PrintAnswerTests(unittest.IsolatedAsyncioTestCase):
    def state(self, node):
        root = node.removesuffix("_details")
        state = tree.initial_state()
        for label in ("АТОЛ FPrint-22ПТК", "Бумага и печать"):
            state, _ = tree.advance(state, label)
        label = next(c["label"] for c in tree.catalog()["nodes"]["group_print"]["choices"] if c["next"] == root)
        state, _ = tree.advance(state, label)
        if node != root:
            state, _ = tree.advance(state, "Показать, где изменить яркость")
        return state

    def model(self, data):
        return SimpleNamespace(route_support=Mock(return_value=json.dumps(data)))

    async def test_every_added_choice_has_equivalent_free_text_transition(self):
        cases = {
            "jam": ["Убрал смятую бумагу, что дальше", "Не смог открыть крышку"],
            "blank": ["Где находится настройка яркости", "Теперь текст появился", "После проверки все еще пустой чек", "Не могу открыть программу"],
            "heat": ["Покажи как менять яркость", "Остыло, теперь печатает нормально", "Проверил, опять перегрев", "Не могу открыть настройки"],
            "blank_details": ["Теперь текст появился", "После проверки все еще пустой чек", "Не смог открыть программу"],
            "heat_details": ["Остыло, теперь печатает нормально", "Проверил, опять перегрев", "Не могу открыть настройки"],
            "dots": ["Давайте вызовем мастера"],
        }
        for node, messages in cases.items():
            for index, message in enumerate(messages):
                with self.subTest(node=node, message=message):
                    state = self.state(node)
                    label = tree.catalog()["nodes"][node]["choices"][index]["label"]
                    expected, expected_text = tree.advance(state, label)
                    result, text = await advance(state, message, [], self.model({"question": node, "choice": index}))
                    self.assertEqual(text, expected_text)
                    self.assertEqual(result["_atol_tree"]["node"], expected["_atol_tree"]["node"])
                    self.assertEqual(result.get("performed_checks"), expected.get("performed_checks"))

    async def test_unknown_does_not_imply_failure_or_success(self):
        for node in ("blank", "heat", "blank_details", "heat_details", "jam", "dots"):
            state = self.state(node)
            for message in ("Не знаю, помогло ли", "Еще не пробовал", "Не уверен", "Головка остыла"):
                for choice in range(len(tree.catalog()["nodes"][node]["choices"])):
                    result, _ = await advance(state, message, [], self.model({"question": node, "choice": choice}))
                    self.assertEqual(result["_atol_tree"], state["_atol_tree"], (node, message, choice))
                    self.assertNotIn("performed_checks", result)

    async def test_problem_correction_requires_confirmation_and_can_be_rejected(self):
        state = self.state("blank_details")
        state["paper_facts"] = {"Ширина ленты": "80 мм"}
        state["_atol_tree"]["answers"] = [{"node": "width", "field": "Ширина ленты", "value": "80 мм"}]
        original = deepcopy(state)
        result, _ = await advance(state, "Ошибся, на чеке пропадают точки", [], self.model({"targets": ["dots"]}))
        self.assertEqual(state, original)
        self.assertEqual(result["paper_facts"], state["paper_facts"])
        self.assertIn("proposal", result["_atol_tree"])
        restored = json.loads(json.dumps(result))
        back, _ = await advance(restored, "Нет", [], None)
        self.assertEqual(back["_atol_tree"]["node"], "blank_details")
        self.assertEqual(back["paper_facts"], state["paper_facts"])
        confirmed, _ = await advance(result, tree.choices(result)[0]["label"], [], None)
        self.assertEqual(confirmed["_atol_tree"]["node"], "dots")
        self.assertNotIn("paper_facts", confirmed)
        self.assertNotIn("answers", confirmed["_atol_tree"])
        self.assertEqual(confirmed["problem_changes"][-1]["previous_facts"], state["paper_facts"])
        self.assertNotIn("performed_checks", confirmed)

    async def test_buttons_and_details_do_not_call_model_or_mark_success(self):
        model = self.model({})
        for node in ("jam", "blank", "heat", "blank_details", "heat_details", "dots"):
            state = self.state(node)
            for choice in tree.choices(state):
                await advance(state, choice["label"], [], model)
        model.route_support.assert_not_called()

    async def test_unavailable_model_preserves_the_current_check(self):
        for node in ("jam", "blank", "heat", "dots"):
            state = self.state(node)
            model = SimpleNamespace(route_support=Mock(side_effect=RuntimeError("unavailable")))
            result, _ = await advance(state, "Ничего не понятно", [], model)
            self.assertEqual(result["_atol_tree"], state["_atol_tree"])
            self.assertEqual(tree.choices(result), tree.choices(state))
        result, _ = await advance(self.state("heat"), "Где изменить яркость", [], None)
        self.assertEqual(result["_atol_tree"]["node"], "heat_details")
        self.assertNotIn("performed_checks", result)

    async def test_removal_question_is_not_a_request_to_load_new_paper(self):
        state = self.state("jam")
        result, _ = await advance(state, "Покажи как убрать смятую бумагу", [], self.model({"question": "jam", "choice": 0}))
        self.assertEqual(result["_atol_tree"], state["_atol_tree"])

    def test_configured_indices_match_existing_nodes(self):
        data = configuration()
        for node in data["nodes"]:
            choices = tree.catalog()["nodes"][node]["choices"]
            policy = data["validation"].get(data["validation_groups"].get(node, node), {})
            for section in ("explicit", "evidence", "negated"):
                self.assertTrue(all(0 <= int(i) < len(choices) for i in policy.get(section, {})), node)

    def test_named_model_choices_follow_the_current_question(self):
        for node in ("jam", "blank", "blank_details", "heat", "heat_details", "dots"):
            allowed = questions(self.state(node))
            for index, choice in enumerate(tree.catalog()["nodes"][node]["choices"]):
                raw = json.dumps({"question": node, "choice": choice["label"]})
                self.assertEqual(parse_answer(raw, allowed), (node, index))
            with self.assertRaises(ValueError):
                parse_answer(json.dumps({"question": node, "choice": "Придуманная инструкция"}), allowed)

    def test_optional_details_do_not_replace_the_result_question(self):
        for node in ("blank", "heat", "blank_details", "heat_details"):
            self.assertEqual(questions(self.state(node))[node]["text"], "Помогло после выполнения инструкции?")


if __name__ == "__main__":
    unittest.main()
