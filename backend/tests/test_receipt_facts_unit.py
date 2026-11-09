"""Fact-level contract tests. No model, database, Docker or holdout access."""

import json
import unittest
from copy import deepcopy
from pathlib import Path

from src.services.receipt_choices import choices_for
from src.services.receipt_diagnosis import respond_receipt
from src.services.receipt_facts import ALIASES, SELECTION_FACTS, collect_facts
from src.services.receipt_procedures import catalog

DATA = Path(__file__).resolve().parents[1] / "data" / "receipt_dialogues"


class ReferenceFactTests(unittest.TestCase):
    def test_development_fact_projection(self):
        for line in (
            (DATA / "development.jsonl").read_text(encoding="utf-8").splitlines()
        ):
            dialogue = json.loads(line)
            flow = {
                "facts": deepcopy(dialogue["initial_context"].get("verified_facts", {}))
            }
            pending = (
                dialogue["initial_context"].get("pending_question", {}).get("fact")
            )
            for index, turn in enumerate(dialogue["turns"]):
                # The preceding question is a fixture at this unit-test boundary.
                # This does not assert that the real planner selected that question.
                if not turn["user"].get("button", {}).get("question_id"):
                    collect_facts(flow, turn["user"]["text"], pending)
                for key, value in turn["expect"]["must_record"].items():
                    if key not in SELECTION_FACTS:
                        continue
                    with self.subTest(dialogue=dialogue["id"], turn=index, fact=key):
                        self.assertIn(key, flow["facts"])
                        self.assertEqual(flow["facts"].get(key), value)
                actions = turn["expect"]["allowed_next_actions"]
                pending = next(
                    (a.get("fact") for a in actions if a["type"] == "ask_fact"), None
                )
                offered = next(
                    (a for a in actions if a["type"] == "offer_procedure"), None
                )
                if offered:
                    procedure = next(
                        p
                        for p in catalog()["procedures"]
                        if p["id"] == offered["procedure_id"]
                    )
                    pending = {
                        "collect_print_setting": "print_disabled",
                        "collect_paper_presence": "paper_present",
                        "collect_connection_result": "fito_connected",
                    }.get(procedure["on_success"], "result")

    def test_reported_error_is_not_observation(self):
        for message in (
            "Рулон установлен, но пишет «Нет бумаги»",
            "Пишет нет бумаги, хотя рулон установлен",
            "На экране «Нет бумаги», рулон установлен",
            "Пишет нет бумаги, рулон установлен",
        ):
            flow = {}
            collect_facts(flow, message)
            self.assertIs(flow["facts"]["paper_present"], True)
            self.assertEqual(flow["facts"]["exact_error"].casefold(), "нет бумаги")

    def test_no_only_answers_current_question(self):
        for pending, expected in (
            ("paper", False),
            ("error", True),
            ("model", True),
            (None, True),
        ):
            flow = {"facts": {"paper_present": True}}
            collect_facts(flow, "нет", pending)
            self.assertIs(flow["facts"]["paper_present"], expected)

    def test_unknown_is_not_false(self):
        flow = {"facts": {"paper_present": True}}
        collect_facts(flow, "Не могу проверить", "paper")
        self.assertIsNone(flow["facts"]["paper_present"])
        self.assertFalse(flow["paper_missing"])

    def test_unreadable_is_scoped_to_question(self):
        for pending, key in (("model", "model"), ("error", "exact_error")):
            flow = {}
            collect_facts(flow, "Не могу прочитать", pending)
            self.assertIsNone(flow["facts"][key])
            if pending == "model":
                self.assertNotIn("exact_error", flow["facts"])

    def test_all_reference_conflicts_stay_unknown_until_clarified(self):
        for line in (
            (DATA / "development.jsonl").read_text(encoding="utf-8").splitlines()
        ):
            dialogue = json.loads(line)
            if dialogue["variant"] != "contradiction":
                continue
            flow = {
                "facts": deepcopy(dialogue["initial_context"].get("verified_facts", {}))
            }
            collect_facts(flow, dialogue["turns"][0]["user"]["text"])
            with self.subTest(dialogue=dialogue["id"]):
                self.assertIsNone(flow["facts"]["model"])
                self.assertIn("model", flow["fact_conflicts"])
            collect_facts(flow, dialogue["turns"][1]["user"]["text"], "model")
            self.assertNotIn("model", flow["fact_conflicts"])

    def test_paper_conflict_and_correction(self):
        flow = {}
        collect_facts(flow, "Рулон есть, но бумаги нет")
        self.assertIn("paper_present", flow["fact_conflicts"])
        collect_facts(flow, "Ошибся, бумаги нет", "paper")
        self.assertIs(flow["facts"]["paper_present"], False)
        self.assertNotIn("paper_present", flow["fact_conflicts"])

    def test_error_word_is_not_a_correction_marker(self):
        flow = {}
        collect_facts(flow, "Ошибка печати. Рулон есть, бумаги нет")
        self.assertIn("paper_present", flow["fact_conflicts"])
        flow = {}
        collect_facts(flow, "Уточняю: рулон есть и бумаги нет")
        self.assertIn("paper_present", flow["fact_conflicts"])

    def test_explicit_temporal_correction(self):
        flow = {}
        collect_facts(flow, "Раньше бумага была, а теперь бумаги нет")
        self.assertIs(flow["facts"]["paper_present"], False)
        collect_facts(flow, "Сказал Пирит 2Ф, поправлю: Вики Принт 80")
        self.assertEqual(flow["facts"]["model"], "Вики Принт 80")

    def test_model_change_invalidates_settings_not_new_observations(self):
        flow = {
            "facts": {
                "model": "АТОЛ FPrint-22ПТК",
                "platform": "5.0",
                "paper_width_mm": 80,
                "driver_width_mm": 80,
                "paper_present": True,
            }
        }
        collect_facts(flow, "Ошибся: Пирит 2Ф. Бумаги нет")
        self.assertEqual(flow["facts"]["model"], "Пирит 2Ф")
        self.assertIs(flow["facts"]["paper_present"], False)
        for field in ("platform", "paper_width_mm", "driver_width_mm"):
            self.assertNotIn(field, flow["facts"])

    def test_non_observations_do_not_create_facts(self):
        for message in (
            "Есть запасной рулон термобумаги",
            "Какой рулон установить?",
            "Перезагрузка не помогла",
            "лдфыврфдлоыва",
            "Бумага есть?",
            "Если бумаги нет, что делать?",
            "Бумага не закончилась",
        ):
            flow = {}
            collect_facts(flow, message)
            self.assertNotIn("paper_present", flow["facts"])

    def test_neighbor_and_guess_do_not_replace_model(self):
        flow = {"facts": {"model": "Вики Принт"}}
        collect_facts(flow, "У коллеги Пирит 2Ф. Как у него работает?")
        self.assertEqual(flow["facts"]["model"], "Вики Принт")
        collect_facts(flow, "На наклейке вроде Пирит 2Ф, но не знаю, чему верить")
        self.assertIsNone(flow["facts"]["model"])
        self.assertIn("model", flow["fact_conflicts"])

    def test_no_error_does_not_mean_missing_qr(self):
        flow = {}
        collect_facts(flow, "Ошибки нет, QR печатается")
        self.assertNotIn("symptom", flow["facts"])

    def test_no_error_does_not_mean_missing_paper(self):
        flow = {}
        collect_facts(flow, "Бумага есть, ошибки нет")
        self.assertIs(flow["facts"]["paper_present"], True)
        self.assertNotIn("paper_present", flow["fact_conflicts"])
        for text in ("Запасной рулон есть", "Рулон есть на полке"):
            flow = {}
            collect_facts(flow, text)
            self.assertNotIn("paper_present", flow["facts"])

    def test_unknown_error_distinct_from_no_error(self):
        for reply, status in (("нет", "absent"), ("Не могу прочитать", "unknown")):
            flow = {}
            collect_facts(flow, reply, "error")
            self.assertIsNone(flow["facts"]["exact_error"])
            self.assertEqual(flow["facts"]["error_status"], status)

    def test_negative_model_and_opposite_symptoms(self):
        flow = {}
        collect_facts(flow, "Это не Пирит 2Ф, а Вики Принт 57")
        self.assertEqual(flow["facts"]["model"], "Вики Принт 57")
        collect_facts(flow, "Лента не выходит. Лента выходит совершенно пустая.")
        self.assertIn("symptom", flow["fact_conflicts"])


class ReceiptDialogueTests(unittest.IsolatedAsyncioTestCase):
    async def test_reference_replays_never_ask_known_fact(self):
        for line in (
            (DATA / "development.jsonl").read_text(encoding="utf-8").splitlines()
        ):
            dialogue = json.loads(line)
            state = {
                "_receipt": {
                    "facts": deepcopy(
                        dialogue["initial_context"].get("verified_facts", {})
                    )
                }
            }
            for index, turn in enumerate(dialogue["turns"]):
                state, _ = await respond_receipt(state, turn["user"]["text"], None)
                flow = state["_receipt"]
                pending = ALIASES.get(flow.get("pending"), flow.get("pending"))
                if (
                    pending is None
                    or pending == "result"
                    or pending in flow.get("fact_conflicts", {})
                ):
                    continue
                with self.subTest(dialogue=dialogue["id"], turn=index, pending=pending):
                    self.assertIsNone(flow["facts"].get(pending))

    async def test_skip_facts_supplied_together(self):
        state, _ = await respond_receipt(
            {},
            "АТОЛ FPrint-22ПТК не печатает чек. Бамаги нет. Стоит горизонтально, лента 80 мм",
            None,
        )
        self.assertNotIn("pending", state["_receipt"])
        self.assertEqual(state["_receipt"]["width"], "80")

    async def test_unknown_and_unrecognized_do_not_loop(self):
        state, _ = await respond_receipt({}, "Пирит 2Ф не печатает чек", None)
        state, _ = await respond_receipt(state, "Не знаю", None)
        self.assertEqual(state["_phase"], "confirm")
        self.assertIsNone(state["receipt_facts"]["paper_present"])
        state, _ = await respond_receipt({}, "не печатает чек", None)
        for _ in range(2):
            state, _ = await respond_receipt(state, "аааббб", None)
        self.assertEqual(state["_phase"], "confirm")

    async def test_paper_observation_in_error_answer(self):
        state = {
            "_receipt": {
                "model": "Пирит 2Ф",
                "symptom": "чек не печатается",
                "paper": "present",
                "pending": "error",
            }
        }
        state, _ = await respond_receipt(
            state, "Поправлю: бумаги нет, ошибки нет", None
        )
        self.assertIs(state["receipt_facts"]["paper_present"], False)
        self.assertEqual(state["receipt_facts"]["error_status"], "absent")

    async def test_correction_during_result_invalidates_old_plan(self):
        state = {
            "sources": [{"title": "old", "url": "old"}],
            "_receipt": {
                "model": "АТОЛ FPrint-22ПТК",
                "symptom": "чек не печатается",
                "paper": "absent",
                "layout": "horizontal",
                "width": "80",
                "pending": "result",
                "active_procedure": "old",
            },
        }
        state, _ = await respond_receipt(
            state, "Я перепутал, на наклейке Пирит 2Ф", None
        )
        self.assertNotEqual(state["_phase"], "resolved")
        self.assertNotIn("sources", state)
        self.assertNotIn("active_procedure", state["_receipt"])
        self.assertIsNone(state["_receipt"]["width"])

    async def test_repeated_question_has_new_choice_identity(self):
        state, _ = await respond_receipt({}, "не печатает чек", None)
        old = choices_for(state)
        state, _ = await respond_receipt(state, "непонятный ответ", None)
        self.assertTrue(old)
        self.assertTrue(choices_for(state))
        self.assertFalse({x["id"] for x in old} & {x["id"] for x in choices_for(state)})

    async def test_result_with_updated_paper_does_not_repeat_lookup(self):
        async def unexpected_lookup(*args):
            self.fail("A failed check must not be repeated")

        state = {
            "_receipt": {
                "model": "Пирит 2Ф",
                "paper": "absent",
                "symptom": "чек не печатается",
                "pending": "result",
            }
        }
        state, _ = await respond_receipt(
            state, "Не помогло, бумага есть", unexpected_lookup
        )
        self.assertIs(state["receipt_facts"]["paper_present"], True)
        self.assertIs(state["receipt_facts"]["problem_resolved"], False)
        self.assertEqual(state["_phase"], "confirm")

    async def test_success_is_explicit_not_inferred_from_indicator(self):
        initial = {
            "_receipt": {
                "model": "Пирит 2Ф",
                "paper": "absent",
                "symptom": "чек не печатается",
                "pending": "result",
            }
        }
        state, _ = await respond_receipt(initial, "Зелёный постоянно горит", None)
        self.assertNotEqual(state["_phase"], "resolved")
        state, _ = await respond_receipt(
            initial, "Выполнил, теперь обычный чек печатается", None
        )
        self.assertEqual(state["_phase"], "resolved")


if __name__ == "__main__":
    unittest.main()
