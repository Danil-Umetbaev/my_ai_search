"""Procedure and dialogue contracts; no Docker, model or reserved holdout."""

import unittest
from copy import deepcopy
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.equipment_scope import (
    canonical_model,
    document_matches,
    model_matches,
)
from src.services.receipt_choices import choice_fact, choices_for
from src.services.receipt_diagnosis import respond_receipt
from src.services.receipt_facts import collect_facts
from src.services.receipt_procedures import (
    catalog,
    infer_intent,
    render_procedure,
    select_procedure,
)
from src.services.support_knowledge import SupportKnowledgeService
from src.services.support_retrieval import retrieve_materials


def matching_facts(procedure):
    return {
        r["fact"]: r["equals"] if "equals" in r else r["one_of"][0]
        for r in procedure["applicability"]["all_of"]
    }


def source_documents():
    return [
        {
            "id": source["document_id"],
            "checksum": source["checksum"],
            "title": source["title"],
            "content": "",
            "source_url": source["url"],
        }
        for source in catalog()["sources"].values()
    ]


class ProcedureTests(unittest.TestCase):
    def test_every_catalog_procedure_and_alternative(self):
        for procedure in catalog()["procedures"]:
            conditions = procedure["applicability"]["all_of"]
            combinations = product(
                *(r.get("one_of", [r.get("equals")]) for r in conditions)
            )
            for values in combinations:
                for intent in procedure["routing"]["intents"]:
                    with self.subTest(
                        procedure=procedure["id"], intent=intent, values=values
                    ):
                        result = select_procedure(
                            dict(zip((r["fact"] for r in conditions), values)), intent
                        )
                        self.assertEqual(result["procedure"]["id"], procedure["id"])
                        self.assertEqual(
                            result["status"],
                            "selected" if procedure["status"] == "ready" else "blocked",
                        )

    def test_every_required_condition_is_enforced(self):
        for procedure in catalog()["procedures"]:
            if procedure["status"] != "ready":
                continue
            facts = matching_facts(procedure)
            for key, value in facts.items():
                for change in ("remove", "unknown", "wrong"):
                    changed = deepcopy(facts)
                    if change == "remove":
                        del changed[key]
                    else:
                        changed[key] = (
                            None
                            if change == "unknown"
                            else (not value if type(value) is bool else "incompatible")
                        )
                    with self.subTest(
                        procedure=procedure["id"], key=key, change=change
                    ):
                        result = select_procedure(
                            changed, procedure["routing"]["intents"][0]
                        )
                        self.assertNotEqual(result["status"], "selected")
                        if result["status"] == "clarify":
                            self.assertNotIn(result["field"], changed)

    def test_sources_and_restrictions_are_preserved(self):
        documents = source_documents()
        for procedure in catalog()["procedures"]:
            with self.subTest(procedure=procedure["id"]):
                result = render_procedure(procedure, documents)
                if procedure["status"] != "ready":
                    self.assertEqual(result["status"], "blocked")
                    continue
                self.assertEqual(result["status"], "answered")
                for text in (
                    procedure["documentation_restrictions"]
                    + procedure["product_limits"]
                ):
                    self.assertIn(text, result["answer"])
                for step in procedure["steps"]:
                    self.assertIn(step["action"], result["answer"])
                self.assertEqual(render_procedure(procedure, [])["status"], "blocked")
                changed = deepcopy(documents)
                for doc in changed:
                    doc["checksum"] = "changed"
                self.assertEqual(
                    render_procedure(procedure, changed)["status"], "blocked"
                )
                if procedure["required_materials"]:
                    self.assertEqual(
                        render_procedure(procedure, documents, Path(__file__).parent)[
                            "status"
                        ],
                        "blocked",
                    )

    def test_no_foreign_model(self):
        for procedure in catalog()["procedures"]:
            facts = matching_facts(procedure)
            expected = facts["model"]
            for model in (
                "АТОЛ FPrint-22ПТК",
                "Пирит 2Ф",
                "Вики Принт",
                "Вики Принт 57",
                "Вики Принт 80",
            ):
                facts["model"] = model
                result = select_procedure(facts, procedure["routing"]["intents"][0])
                if not model_matches(model, expected):
                    self.assertNotEqual(
                        result.get("procedure", {}).get("id"), procedure["id"]
                    )

    def test_model_and_production_limits_before_ranking(self):
        self.assertIsNone(canonical_model("АТОЛ FPrint-22Ф"))
        self.assertIsNone(canonical_model("АТОЛ FPrint-22"))
        documents = [
            {
                "id": "pirit",
                "title": "Пирит 2Ф",
                "content": "Замена бумаги",
                "source_url": "",
                "checksum": "1",
            },
            {
                "id": "viki",
                "title": "Вики Принт 80",
                "content": "Замена бумаги",
                "source_url": "",
                "checksum": "2",
            },
            {
                "id": "cutter",
                "title": "Замена ножа",
                "content": "Подходит только для Вики Принт 57 Плюс Ф начиная с 2025 года. Замена бумаги",
                "source_url": "/kb/viki-printy/knife",
                "checksum": "3",
            },
        ]
        for facts, expected in (
            ({"model": "Пирит 2Ф"}, ["pirit"]),
            ({"model": "Вики Принт"}, []),
            ({"model": "Вики Принт 57 Плюс Ф"}, []),
            ({"model": "Вики Принт 57 Плюс Ф", "production_year": 2025}, ["cutter"]),
            ({"model": "Вики Принт 80"}, ["viki"]),
        ):
            self.assertEqual(
                [
                    item["document_id"]
                    for item in retrieve_materials(documents, "Замена бумаги", facts)
                ],
                expected,
            )
        self.assertFalse(
            document_matches(
                {"title": "FPrint-22ПТК", "software_version": "5.0"},
                {"model": "АТОЛ FPrint-22ПТК", "platform": "2.5"},
            )
        )

    def test_intents_do_not_confuse_connection_statement_with_request(self):
        self.assertEqual(
            infer_intent(
                "Нужен диагностический отчет, Fito уже связалась с кассой", {}
            ),
            "diagnostic_report",
        )
        self.assertEqual(
            infer_intent(
                "Не печатает чек, Fito уже связалась",
                {"symptom": "no_paper_output", "paper_present": True},
            ),
            "paper_feed",
        )

    def test_short_answers_to_catalog_questions(self):
        for field, answer, expected in (
            ("platform", "5.0", "5.0"),
            ("connection_type", "ComProxy", "comproxy"),
            ("paper_indicator", "Красный", "red"),
            ("paper_indicator", "Не горит", "off"),
            ("printing_stopped", "Не знаю", None),
        ):
            flow = {}
            collect_facts(flow, answer, field)
            self.assertIn(field, flow["facts"])
            self.assertEqual(flow["facts"][field], expected)

    def test_corrected_symptom_overrides_original_question(self):
        self.assertEqual(
            infer_intent(
                "Бумага замялась. Исправляю: выходит пустой чек",
                {"symptom": "blank_print", "paper_present": True},
            ),
            "print_quality",
        )


class KnowledgeDialogueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(
            documents=SimpleNamespace(
                get_support_documents=AsyncMock(return_value=source_documents())
            )
        )
        self.service = SupportKnowledgeService(self.db)

    async def lookup(self, query, flow):
        return await self.service.lookup(query, flow, "it")

    async def test_all_ready_procedures_through_dialogue(self):
        queries = {
            "paper_installation": "Нужно заправить бумагу",
            "paper_jam": "Замялась бумага",
            "paper_skew": "Перекос бумаги",
            "diagnostic_report": "Нужен диагностический отчет",
            "connection": "Как настроить связь с кассой?",
            "read_print_setting": "Как проверить запрет печати?",
            "paper_presence": "Как проверить наличие бумаги?",
        }
        for procedure in catalog()["procedures"]:
            if procedure["status"] != "ready":
                continue
            with self.subTest(procedure=procedure["id"]):
                facts = matching_facts(procedure)
                state, answer = await respond_receipt(
                    {"_receipt": {"facts": facts}},
                    queries[procedure["routing"]["intents"][0]],
                    self.lookup,
                )
                self.assertEqual(
                    state["_receipt"].get("active_procedure"), procedure["id"], answer
                )
                self.assertEqual(state["_phase"], "diagnosing")

    async def test_each_ready_procedure_can_be_reached_with_buttons(self):
        queries = {
            "paper_installation": "Заправить бумагу",
            "paper_jam": "Замялась бумага",
            "paper_skew": "Перекос бумаги",
            "diagnostic_report": "Нужен диагностический отчет",
            "connection": "Как настроить связь?",
            "read_print_setting": "Проверить запрет печати",
            "paper_presence": "Проверить наличие бумаги",
        }
        for procedure in catalog()["procedures"]:
            if procedure["status"] != "ready":
                continue
            with self.subTest(procedure=procedure["id"]):
                expected = matching_facts(procedure)
                # Symptom is the initial observation, permission comes from the server.
                initial = {
                    key: value
                    for key, value in expected.items()
                    if key in {"model", "symptom"}
                }
                state, answer = await respond_receipt(
                    {"_receipt": {"facts": initial}},
                    queries[procedure["routing"]["intents"][0]],
                    self.lookup,
                )
                for _ in range(15):
                    flow = state["_receipt"]
                    if flow.get("active_procedure"):
                        break
                    field = flow.get("pending")
                    self.assertIn(field, expected, answer)
                    choices = choices_for(state)
                    selected = next(
                        (
                            item
                            for item in choices
                            if choice_fact(state, item["id"])
                            == {"field": field, "value": expected[field]}
                        ),
                        None,
                    )
                    self.assertIsNotNone(selected, (field, choices))
                    state, answer = await respond_receipt(
                        state,
                        selected["label"],
                        self.lookup,
                        selected_fact=choice_fact(state, selected["id"]),
                    )
                self.assertEqual(
                    state["_receipt"].get("active_procedure"), procedure["id"], answer
                )

    async def test_permissions_are_not_taken_from_user_facts(self):
        procedure = next(
            p for p in catalog()["procedures"] if p["id"] == "viki-connect-direct"
        )
        result = await self.service.lookup(
            "Как настроить связь", {"facts": matching_facts(procedure)}, "kassir"
        )
        self.assertNotIn(result.get("kind"), {"instruction", "diagnostic_check"})

    async def test_known_paper_is_not_overwritten_by_reported_error(self):
        state, answer = await respond_receipt(
            {},
            "Пирит 2Ф не печатает чек. Рулон установлен, но пишет «Нет бумаги»",
            self.lookup,
        )
        self.assertIs(state["receipt_facts"]["paper_present"], True)
        self.assertNotEqual(
            state["_receipt"].get("active_procedure"), "pirit-paper-load"
        )
        self.assertNotEqual(state["_receipt"].get("pending"), "paper_present")

    async def test_diagnostic_success_is_not_original_problem_resolved(self):
        state = {
            "problem": "Не печатает чек",
            "_receipt": {
                "facts": {
                    "model": "Вики Принт",
                    "paper_present": True,
                    "symptom": "no_paper_output",
                },
                "pending": "procedure_result",
                "result_action": "collect_connection_result",
                "active_procedure": "viki-connect-direct",
            },
        }
        state, answer = await respond_receipt(state, "Да", self.lookup)
        self.assertIs(state["receipt_facts"]["fito_connected"], True)
        self.assertNotEqual(state["_phase"], "resolved")
        self.assertIn("viki-connect-direct", state["_receipt"]["completed_procedures"])

    async def test_paper_check_records_answer_and_does_not_loop(self):
        state = {
            "problem": "Не печатает чек",
            "_receipt": {
                "facts": {"model": "Вики Принт"},
                "pending": "procedure_result",
                "result_action": "collect_paper_presence",
                "active_procedure": "viki-paper-presence",
            },
        }
        state, answer = await respond_receipt(state, "Нет", self.lookup)
        self.assertIs(state["receipt_facts"]["paper_present"], False)
        self.assertEqual(state["_phase"], "confirm")
        self.assertNotIn("Заявка создана", answer)

    async def test_model_correction_discards_old_procedure(self):
        state = {
            "problem": "Не печатает чек",
            "_receipt": {
                "facts": {
                    "model": "АТОЛ FPrint-22ПТК",
                    "platform": "5.0",
                    "paper_present": False,
                    "layout": "vertical",
                },
                "pending": "result",
                "active_procedure": "atol-paper-80-vertical",
            },
        }
        state, answer = await respond_receipt(
            state, "Ошибся, это Пирит 2Ф", self.lookup
        )
        self.assertEqual(state["receipt_facts"]["model"], "Пирит 2Ф")
        self.assertNotIn("layout", state["receipt_facts"])
        self.assertNotEqual(
            state["_receipt"].get("active_procedure"), "atol-paper-80-vertical"
        )
        self.assertEqual(state["_phase"], "diagnosing")

    async def test_model_change_clears_retrieved_materials(self):
        state = {
            "problem": "Не печатает чек",
            "retrieved_materials": [{"title": "АТОЛ"}],
            "_receipt": {"facts": {"model": "АТОЛ FPrint-22ПТК"}},
        }
        state, _ = await respond_receipt(state, "Ошибся, это Пирит 2Ф", self.lookup)
        self.assertNotIn("retrieved_materials", state)
