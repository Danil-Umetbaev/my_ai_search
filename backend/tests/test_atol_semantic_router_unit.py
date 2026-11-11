import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.services import atol_semantic_router as router
from src.services.atol_support_tree import advance, initial_state, choices


class SemanticRoutingTests(unittest.IsolatedAsyncioTestCase):
    def selected_model(self):
        return advance(initial_state(), "АТОЛ FPrint-22ПТК")[0]

    async def test_free_text_is_proposed_not_executed(self):
        for message, target in (
            ("касса заблокирована", "group_errors"),
            ("с печатью непонятки", "group_print"),
            ("жует ленту", "jam"),
        ):
            with self.subTest(message=message):
                llm = SimpleNamespace(route_support=Mock(return_value=json.dumps({"targets": [target]})))
                state, answer = await router.advance(self.selected_model(), message, [], llm)
                self.assertEqual(state["_atol_tree"]["node"], "categories")
                self.assertEqual(state["_atol_tree"]["proposal"]["targets"], [target])
                self.assertNotIn("performed_checks", state)
                self.assertNotIn("sources", state)
                confirmed, _ = await router.advance(state, choices(state)[0]["label"], [], llm)
                self.assertEqual(confirmed["_atol_tree"]["node"], target)
                llm.route_support.assert_called_once()

    async def test_buttons_never_call_model(self):
        llm = SimpleNamespace(route_support=Mock(side_effect=AssertionError("Model called for button")))
        state = initial_state()
        for label in ("АТОЛ FPrint-22ПТК", "Бумага и печать", "Зажевало бумагу"):
            state, _ = await router.advance(state, label, [], llm, button=True)
        self.assertEqual(state["_atol_tree"]["node"], "jam")
        llm.route_support.assert_not_called()

    async def test_failures_leave_buttons_and_rule_fallback(self):
        for failure in (TimeoutError(), RuntimeError("unavailable")):
            with patch.object(router, "run_support_model", AsyncMock(side_effect=failure)):
                state, _ = await router.advance(self.selected_model(), "Зажевало ленту", [], SimpleNamespace(route_support=Mock()))
                self.assertEqual(state["_atol_tree"]["proposal"]["targets"], ["jam"])
                self.assertTrue(choices(state))
        state, _ = await router.advance(self.selected_model(), "с печатью непонятки", [], None)
        self.assertEqual(state["_atol_tree"]["node"], "categories")
        self.assertTrue(choices(state))

    async def test_unknown_and_invalid_ids_cannot_execute_instructions(self):
        for raw in ('{"targets":["paper80h"]}', '{"targets":["resolved"]}',
                    '{"targets":["handoff"]}', '{"targets":["model"]}',
                    '{"targets":[],"instruction":"перезагрузите"}', 'not json'):
            llm = SimpleNamespace(route_support=Mock(return_value=raw))
            state, _ = await router.advance(self.selected_model(), "с печатью непонятки", [], llm)
            self.assertEqual(state["_atol_tree"]["node"], "categories")
            self.assertEqual(state["_atol_tree"]["proposal"]["targets"], [])

    async def test_previous_description_cannot_override_current_message(self):
        history = [{"role": "user", "content": "касса заблокирована"}]
        llm = SimpleNamespace(route_support=Mock(return_value='{"targets":["group_print"]}'))
        state, _ = await router.advance(self.selected_model(), "нет, с печатью непонятки", history, llm)
        payload = json.loads(llm.route_support.call_args.args[1])
        self.assertEqual(payload["message"], "нет, с печатью непонятки")
        self.assertNotIn("history", payload)
        self.assertNotIn("касса заблокирована", payload["question"] + payload["message"])
        self.assertEqual(state["_atol_tree"]["proposal"]["description"], payload["message"])

    async def test_explicit_other_model_cannot_enter_atol_branch(self):
        llm = SimpleNamespace(route_support=Mock(return_value='{"targets":["group_print"]}'))
        for message in ("Вики Принт не печатает", "Пирит жует ленту", "АТОЛ 55 не печатает"):
            state, answer = await router.advance(self.selected_model(), message, [], llm)
            self.assertEqual(state["_atol_tree"]["proposal"]["targets"], [])
            self.assertIn("другая касса", answer)
        llm.route_support.assert_not_called()

    def test_response_schema_rejects_mixed_or_invalid_targets(self):
        for targets in ("jam", [True], [{}], ["jam", "jam"], ["group_print", "jam"], ["pc"] * 4):
            with self.assertRaises(ValueError):
                router.parse_targets(json.dumps({"targets": targets}))


if __name__ == "__main__":
    unittest.main()
