"""Answer/outcome contracts using the development dialogues, not the holdout."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.services.receipt_diagnosis import respond_receipt
from src.services.receipt_procedures import (
    DATA,
    catalog,
    render_procedure,
    condition_matches,
)
from src.services.receipt_reference import reference_notes, explain_reference
from src.services.support_knowledge import SupportKnowledgeService


def documents():
    return [
        {
            "id": v["document_id"],
            "checksum": v["checksum"],
            "title": v["title"],
            "content": "",
            "source_url": v["url"],
        }
        for v in catalog()["sources"].values()
    ]


class AnswerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = SimpleNamespace(
            get_support_documents=AsyncMock(return_value=documents())
        )
        self.service = SupportKnowledgeService(
            SimpleNamespace(documents=self.repository)
        )

    async def lookup(self, query, flow):
        return await self.service.lookup(query, flow, "it")

    async def test_development_dialogues_answer_contract(self):
        procedures = {p["id"]: p for p in catalog()["procedures"]}
        checked = 0
        for line in (
            (DATA / "receipt_dialogues/development.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            dialogue = json.loads(line)
            if dialogue["target"]["kind"] == "shared":
                continue
            initial = dialogue["initial_context"]
            state = {
                "problem": initial.get(
                    "problem_description", dialogue["turns"][0]["user"]["text"]
                ),
                "_receipt": {"facts": deepcopy(initial.get("verified_facts", {}))},
            }
            if initial.get("pending_question"):
                state["_receipt"]["pending"] = initial["pending_question"]["fact"]
            environment = dialogue["environment"]
            role = (
                "it" if environment.get("allowed_operator", True) is True else "kassir"
            )
            repo = SimpleNamespace(
                get_support_documents=AsyncMock(
                    return_value=(
                        documents() if environment["source_checksums_match"] else []
                    )
                )
            )
            service = SupportKnowledgeService(SimpleNamespace(documents=repo))

            async def lookup(query, flow):
                return await service.lookup(query, flow, role)

            def render(procedure, sources):
                return render_procedure(
                    procedure,
                    sources,
                    (
                        DATA
                        if environment["materials_available"]
                        else Path(__file__).parent
                    ),
                )

            for index, turn in enumerate(dialogue["turns"]):
                with self.subTest(dialogue=dialogue["id"], turn=index), patch(
                    "src.services.support_knowledge.render_procedure", render
                ):
                    state, answer = await respond_receipt(
                        state, turn["user"]["text"], lookup
                    )
                    checked += 1
                    allowed = turn["expect"]["allowed_next_actions"]
                    expected = [
                        a["procedure_id"]
                        for a in allowed
                        if a["type"] == "offer_procedure"
                    ]
                    acknowledged = state.get(
                        "next_action"
                    ) == "acknowledge_existing_plan" and any(
                        a["type"] == "acknowledge_existing_plan" for a in allowed
                    )
                    if acknowledged:
                        self.assertIn(
                            state["_receipt"].get("active_procedure"), expected
                        )
                    if expected and not acknowledged:
                        self.assertEqual(
                            state.get("next_action"), "offer_procedure", answer
                        )
                        self.assertIn(state.get("procedure_id"), expected)
                    if state.get("next_action") == "offer_procedure":
                        self.assertTrue(
                            expected
                            or any(
                                a["type"] == "reselect_applicable_procedure"
                                for a in allowed
                            ),
                            answer,
                        )
                        procedure = procedures[state["procedure_id"]]
                        self.assertEqual(procedure["status"], "ready")
                        facts = {
                            **state["receipt_facts"],
                            "allowed_operator": role == "it",
                        }
                        self.assertTrue(
                            all(
                                condition_matches(facts, rule)
                                for rule in procedure["applicability"]["all_of"]
                            )
                        )
                        for step in procedure["steps"]:
                            self.assertIn(step["action"], answer)
                        for restriction in (
                            procedure["documentation_restrictions"]
                            + procedure["product_limits"]
                        ):
                            self.assertIn(restriction, answer)
                    if state.get("next_action") in {
                        "explain_information",
                        "explain_and_offer_specialist",
                        "offer_specialist",
                        "retry_search",
                    }:
                        self.assertNotIn(
                            state["_receipt"].get("pending"),
                            {"result", "procedure_result"},
                        )
                    if "close_resolved" in turn["expect"]["must_not"]:
                        self.assertNotEqual(state["_phase"], "resolved")
        self.assertGreater(checked, 1000)

    async def test_reference_instruction_turns_preserve_every_step_and_limit(self):
        procedures = {p["id"]: p for p in catalog()["procedures"]}
        checked = 0
        for line in (
            (DATA / "receipt_dialogues/development.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            dialogue = json.loads(line)
            first = dialogue["turns"][0]
            expected = [
                a["procedure_id"]
                for a in first["expect"]["allowed_next_actions"]
                if a["type"] == "offer_procedure"
            ]
            if not expected:
                continue
            checked += 1
            with self.subTest(dialogue=dialogue["id"]):
                state = {
                    "_receipt": {
                        "facts": deepcopy(
                            dialogue["initial_context"].get("verified_facts", {})
                        )
                    }
                }
                state, answer = await respond_receipt(
                    state, first["user"]["text"], self.lookup
                )
                self.assertIn(state.get("procedure_id"), expected, answer)
                procedure = procedures[state["procedure_id"]]
                last = -1
                for step in procedure["steps"]:
                    position = answer.index(step["action"])
                    self.assertGreater(position, last)
                    last = position
                for restriction in (
                    procedure["documentation_restrictions"]
                    + procedure["product_limits"]
                ):
                    self.assertIn(restriction, answer)
                self.assertEqual(answer.count(procedure["result_question"]), 1)
                for other in procedures.values():
                    if other["id"] == procedure["id"]:
                        continue
                    unique = {s["action"] for s in other["steps"]} - {
                        s["action"] for s in procedure["steps"]
                    }
                    for action in unique:
                        self.assertNotIn(action, answer)
        self.assertEqual(checked, 110)

    async def test_reference_results_are_not_diagnostic_success(self):
        checked = 0
        for line in (
            (DATA / "receipt_dialogues/development.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            dialogue = json.loads(line)
            if dialogue["variant"] != "diagnostic_result":
                continue
            with self.subTest(dialogue=dialogue["id"]):
                state = {}
                for turn in dialogue["turns"]:
                    state, answer = await respond_receipt(
                        state, turn["user"]["text"], self.lookup
                    )
                self.assertNotEqual(state["_phase"], "resolved", answer)
                self.assertNotEqual(state["_receipt"].get("pending"), "result")
                checked += 1
        self.assertEqual(checked, 19)

    async def test_information_explains_without_result_question(self):
        state, answer = await respond_receipt(
            {}, "Что означает БАТАРЕЯ РАЗРЯЖЕНА на Пирит 2Ф?", self.lookup
        )
        self.assertIn("батареи часов реального времени", answer)
        self.assertEqual(state["next_action"], "explain_information")
        self.assertNotIn("pending", state["_receipt"])
        self.assertNotIn("помог", answer.lower())
        state, reply = await respond_receipt(state, "Спасибо", self.lookup)
        self.assertNotIn("батареи", reply)
        state, reply = await respond_receipt(
            state, "Бумаги нет. Как установить рулон?", self.lookup
        )
        self.assertNotIn("батареи часов", reply)
        self.assertEqual(state["next_action"], "ask_fact")

    async def test_incomplete_instruction_names_missing_material_without_steps(self):
        state, answer = await respond_receipt(
            {}, "Вики Принт не печатает QR-код. Fito подключилась", self.lookup
        )
        self.assertIn("макрос", answer)
        self.assertIn("Не хватает", answer)
        self.assertEqual(state["_phase"], "confirm")
        self.assertNotIn("Запустите", answer)
        self.assertNotIn("pending", state["_receipt"])

    async def test_no_material_is_distinct_from_failure(self):
        state = {"_receipt": {"facts": {"model": "Пирит 2Ф"}}}
        missing = AsyncMock(return_value={"status": "not_found"})
        result, answer = await respond_receipt(state, "Нужны сведения", missing)
        self.assertEqual(result["_phase"], "confirm")
        self.assertIn("не найдена", answer)
        for lookup in (
            AsyncMock(side_effect=RuntimeError("offline")),
            AsyncMock(side_effect=TimeoutError()),
            AsyncMock(return_value={"status": "error"}),
            AsyncMock(return_value={"status": "loading"}),
        ):
            result, answer = await respond_receipt(state, "Нужны сведения", lookup)
            self.assertEqual(result["next_action"], "retry_search")
            self.assertEqual(result["receipt_facts"]["model"], "Пирит 2Ф")
            self.assertNotEqual(result["_phase"], "confirm")
            self.assertNotIn("не найдена", answer)

    async def test_unrecognised_result_does_not_claim_failure(self):
        state = {
            "problem": "Не печатает чек",
            "_receipt": {"facts": {"model": "Пирит 2Ф"}, "pending": "result"},
        }
        state, answer = await respond_receipt(state, "Минутку", self.lookup)
        self.assertEqual(state["_receipt"]["pending"], "result")
        self.assertNotIn("completed_procedures", state["_receipt"])
        self.assertNotEqual(state["_phase"], "resolved")

    async def test_missing_picture_stops_without_guessing(self):
        state = {
            "_receipt": {
                "active_procedure": "pirit-paper-load",
                "pending": "result",
                "facts": {"model": "Пирит 2Ф"},
            }
        }
        state, answer = await respond_receipt(
            state, "Фото загрузки не открывается", self.lookup
        )
        self.assertEqual(state["_phase"], "confirm")
        self.assertIn("материал", answer)
        self.assertNotIn("pending", state["_receipt"])

    async def test_changed_source_cannot_be_reissued_mid_procedure(self):
        state = {
            "problem": "Установка бумаги",
            "_receipt": {
                "active_procedure": "pirit-paper-load",
                "pending": "result",
                "facts": {"model": "Пирит 2Ф"},
            },
        }
        self.repository.get_support_documents.return_value = []
        state, answer = await respond_receipt(state, "Продолжать дальше?", self.lookup)
        self.assertEqual(state["_phase"], "confirm")
        self.assertIn("Источник", answer)

    async def test_overheat_is_not_brightness_increase(self):
        state, answer = await respond_receipt(
            {},
            "На АТОЛ FPrint-22ПТК перегрелась головка. Увеличить яркость?",
            self.lookup,
        )
        self.assertIn("снижение яркости, а не увеличение", answer)
        self.assertNotEqual(state["next_action"], "offer_procedure")

    async def test_absent_overheat_does_not_block_valid_paper_instruction(self):
        procedure = next(
            p for p in catalog()["procedures"] if p["id"] == "atol-paper-58-horizontal"
        )
        facts = {r["fact"]: r["equals"] for r in procedure["applicability"]["all_of"]}
        state, answer = await respond_receipt(
            {"_receipt": {"facts": facts}},
            "Нужно установить рулон. Перегрева головки нет.",
            self.lookup,
        )
        self.assertEqual(state["next_action"], "offer_procedure")
        self.assertEqual(state["procedure_id"], procedure["id"])

    async def test_yes_to_a_condition_does_not_resolve_problem(self):
        state = {
            "problem": "Пирит 2Ф не печатает чек, бумаги нет",
            "_receipt": {
                "facts": {"model": "Пирит 2Ф", "paper_present": False},
                "pending": "cover_accessible",
            },
        }
        state, _ = await respond_receipt(state, "Да", self.lookup)
        self.assertNotEqual(state["_phase"], "resolved")
        self.assertIs(state["receipt_facts"]["cover_accessible"], True)

    async def test_available_replacement_roll_is_not_installed_roll(self):
        state, answer = await respond_receipt(
            {},
            "Нужна инструкция установки рулона. АТОЛ FPrint-22ПТК. Платформа 5.0. Печать остановлена. Крышка открывается. Подходящий рулон есть. Бумаги нет. Горизонтально. Лента 58 мм. Ограничитель есть. В драйвере ширина 58 мм.",
            self.lookup,
        )
        self.assertEqual(state.get("procedure_id"), "atol-paper-58-horizontal", answer)
        self.assertIs(state["receipt_facts"]["paper_present"], False)
        self.assertIs(state["receipt_facts"]["paper_compatible"], True)

    def test_unverified_reference_is_not_explained(self):
        note = next(n for n in reference_notes() if n["id"] == "pirit-battery")
        self.assertIsNone(explain_reference(note, [], {"model": "Пирит 2Ф"}))
        self.assertIsNone(explain_reference(note, documents(), {"model": "Вики Принт"}))
