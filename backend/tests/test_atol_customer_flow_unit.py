import json
import unittest
from unittest.mock import AsyncMock

from src.services import atol_support_tree as tree
from src.services.atol_semantic_router import advance
from src.services.diagnosis import ticket_details


class CustomerFlowTests(unittest.IsolatedAsyncioTestCase):
    async def press(self, state, label, **kwargs):
        self.assertIn(label, [choice["label"] for choice in tree.choices(state)])
        return await advance(state, label, [], button=True, **kwargs)

    async def test_model_five_groups_and_documented_pc_check(self):
        state, _ = await advance(tree.initial_state(), "у нас атол", [])
        self.assertNotIn("environment", state)
        state, _ = await self.press(json.loads(json.dumps(state)), "Да, верно")
        groups = [item for item in tree.available_options(state["_atol_tree"]) if item["next"].startswith("group_")]
        self.assertEqual(len(groups), 5)
        state, _ = await self.press(state, "Касса не реагирует")
        state, _ = await advance(state, "Компьютер не видит кассу", [])
        self.assertEqual(state["_atol_tree"]["node"], "group_response")
        state, answer = await self.press(state, "Программа не видит кассу")
        self.assertIn("Помогло?", answer)
        state, _ = await advance(state, "покажи как проверить связь", [])
        self.assertNotIn("performed_checks", state)
        state, answer = await self.press(state, "Да, верно")
        self.assertIn("Проверка связи", answer)
        state, _ = await advance(state, "Связи с кассой нет", [])
        state, _ = await self.press(state, "Нет, выбрать снова")
        self.assertEqual(state["_atol_tree"]["node"], "pc_details")
        self.assertNotIn("performed_checks", state)

    async def test_other_model_and_offline_description(self):
        for name in ("АТОЛ 55Ф", "не АТОЛ", "ATOL FPrint-55"):
            state, _ = await advance(tree.initial_state(), name, [])
            state, _ = await self.press(state, "Да, верно")
            self.assertEqual(state["_atol_tree"]["node"], "unsupported")
        state, _ = await self.press(tree.initial_state(), "АТОЛ FPrint-22ПТК")
        state, _ = await advance(state, "жужжит, бумага стоит", [])
        self.assertEqual(state["_atol_tree"]["proposal"]["targets"], ["group_print"])
        lookup = AsyncMock()
        state, _ = await advance(state, "на самом деле Пирит", [], lookup=lookup)
        self.assertEqual(state["_atol_tree"]["proposal"]["targets"], [])
        lookup.assert_not_awaited()

    async def test_unmatched_description_evidence_and_handoff(self):
        state, _ = await self.press(tree.initial_state(), "АТОЛ FPrint-22ПТК")
        source = {"title": "Руководство АТОЛ", "url": "https://example.org/manual"}
        lookup = AsyncMock(return_value={
            "kind": "information", "status": "answered", "sources": [source],
            "answer": "Найдены связанные материалы.", "reason": "Применимость не подтверждена.",
        })
        state, answer = await advance(state, "гудит после включения", [], lookup=lookup)
        self.assertEqual(lookup.await_args.args[1]["facts"]["model"], "АТОЛ FPrint-22ПТК")
        self.assertIn(source["title"], answer)
        self.assertNotIn("Помогло?", answer)
        self.assertNotIn("performed_checks", state)
        self.assertTrue(tree.choices(state))
        state, _ = await advance(state, "передать специалисту", [], lookup=lookup)
        self.assertEqual(state["_phase"], "confirm")
        details = ticket_details(state)
        self.assertEqual(details["problem"], "гудит после включения")
        self.assertIn(source, details["sources"])

    async def test_document_clarification_requires_confirmation(self):
        question = {"status": "clarify", "field": "paper_width_mm", "question": "Какая ширина ленты?",
                    "choices": [{"value": 58, "label": "58 мм"}, {"value": 80, "label": "80 мм"}]}
        lookup = AsyncMock(side_effect=[question, {"status": "not_found"}])
        state, _ = await self.press(tree.initial_state(), "АТОЛ FPrint-22ПТК")
        state, answer = await advance(state, "особый сигнал", [], lookup=lookup)
        self.assertEqual(answer, question["question"])
        state, _ = await advance(state, "лента 58 мм", [], lookup=lookup)
        self.assertEqual(state["_atol_tree"]["manual_offer"]["label"], "58 мм")
        lookup.assert_awaited_once()
        state, _ = await self.press(state, "Да, верно", lookup=lookup)
        self.assertEqual(state["receipt_facts"]["paper_width_mm"], 58)
        self.assertEqual(state["_phase"], "confirm")
        self.assertEqual(state["observations"][-1]["answer"], "лента 58 мм")

    async def test_new_symptom_can_replace_unconfirmed_branch(self):
        state, _ = await self.press(tree.initial_state(), "АТОЛ FPrint-22ПТК")
        for label in ("Касса не реагирует", "Кнопка на кассе не работает"):
            state, _ = await self.press(state, label)
        state, _ = await advance(state, "Компьютер не видит кассу", [])
        self.assertEqual(state["_atol_tree"]["node"], "button")
        state, _ = await advance(state, "ОФД не подтверждает чеки", [])
        state, answer = await self.press(state, "ОФД не подтверждает получение чеков")
        self.assertIn("Помогло?", answer)
        self.assertEqual(state["_atol_tree"]["node"], "ofd")
        self.assertEqual(state["problem_changes"][0]["previous"], "Кнопка на кассе не работает")
