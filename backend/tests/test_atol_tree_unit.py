import unittest
from collections import deque

from src.services.atol_support_tree import advance, catalog, choices, initial_state, render


class AtolTreeTests(unittest.TestCase):
    def states(self):
        queue = deque([initial_state()])
        seen = {}
        while queue:
            state = queue.popleft()
            key = state["_atol_tree"]["node"]
            if key in seen:
                continue
            seen[key] = state
            for choice in choices(state):
                updated, _ = advance(state, choice["label"])
                queue.append(updated)
        return seen

    def test_every_node_reachable_and_every_edge_correct(self):
        states = self.states()
        self.assertEqual(set(states), set(catalog()["nodes"]))
        edges = 0
        for key, state in states.items():
            node = catalog()["nodes"][key]
            self.assertTrue(render(state))
            labels = [c["label"] for c in node["choices"]]
            self.assertEqual(len(labels), len(set(labels)))
            for choice in node["choices"]:
                updated, answer = advance(state, choice["label"])
                self.assertEqual(updated["_atol_tree"]["node"], choice["next"], (key, choice))
                self.assertTrue(answer)
                self.assertEqual(state["_atol_tree"]["node"], key)
                edges += 1
        print(f"ATOL: {len(states)} nodes, {edges} transitions covered")

    def test_details_are_not_reported_as_completed_checks(self):
        for key, state in self.states().items():
            for choice in catalog()["nodes"][key]["choices"]:
                if choice.get("action") in {"details", "continue"}:
                    updated, _ = advance(state, choice["label"])
                    self.assertEqual(state.get("performed_checks"), updated.get("performed_checks"))

    def test_paper_failure_needs_actual_error_before_sensor(self):
        for key in ("paper80h", "paper80v", "paper58h", "paper58v", "width_settings"):
            state = self.states()[key]
            updated, _ = advance(state, "Не помогло")
            self.assertEqual(updated["_atol_tree"]["node"], "paper_failed")
            updated, _ = advance(updated, "Другая проблема / не знаю")
            self.assertEqual(updated["_phase"], "confirm")

    def test_outcomes_and_terminal_messages(self):
        for key, state in self.states().items():
            node = catalog()["nodes"][key]
            if any(c["next"] == "resolved" for c in node["choices"]):
                resolved, _ = advance(state, "да")
                self.assertEqual(resolved["_phase"], "resolved")
                self.assertTrue(resolved["performed_checks"])
                unchanged, _ = advance(resolved, "Не помогло")
                self.assertEqual(unchanged, resolved)
            cancelled, _ = advance(state, "отмена")
            if state.get("_phase") != "resolved":
                self.assertEqual(cancelled["_phase"], "cancelled")

    def test_unknown_input_is_preserved_and_not_invented(self):
        state = self.states()["other"]
        updated, _ = advance(state, "Ошибка 9876")
        self.assertEqual(updated["additional_context"], "Ошибка 9876")
        self.assertEqual(updated["_phase"], "confirm")
        declined, _ = advance(updated, "нет")
        self.assertEqual(declined, updated)

    def test_instructions_have_sources_and_sequential_paper_steps(self):
        import re
        for key, node in catalog()["nodes"].items():
            if node["kind"] == "instruction":
                self.assertTrue(node.get("sources"), key)
            if key in {"paper80h", "paper80v", "paper58h", "paper58v"}:
                numbers = [int(x) for x in re.findall(r"^(\d+)\.", node["text"], re.M)]
                self.assertEqual(numbers, list(range(1, len(numbers)+1)))


if __name__ == "__main__":
    unittest.main()
