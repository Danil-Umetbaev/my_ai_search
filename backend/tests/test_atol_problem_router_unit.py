import json
import re
import unittest
from copy import deepcopy

from src.services.atol_problem_router import routing_catalog, suggest
from src.services.atol_support_tree import advance, catalog, choices, initial_state, render


class ProblemRouterTests(unittest.TestCase):
    def selected_model(self):
        return advance(initial_state(), "АТОЛ FPrint-22ПТК")[0]

    def test_reviewed_entries_have_routes_and_valid_patterns(self):
        data = routing_catalog()
        expected = {c["next"] for c in catalog()["nodes"]["menu"]["choices"]} - {"other"}
        self.assertEqual({rule["target"] for rule in data["problems"]}, expected)
        for rule in data["problems"] + data["groups"]:
            self.assertIn(rule["target"], catalog()["nodes"])
            for pattern in rule["patterns"] + rule.get("exclude", []):
                re.compile(pattern)

    def test_symptoms_only_suggest_existing_entries(self):
        examples = {
            "Кнопка промотки не работает": "button",
            "Ошибка даты, касса заблокирована": "date_lock",
            "Ресурс ФН заполнен": "fn",
            "Касса заблокирована из-за ОФД": "ofd_lock",
            "Касса не выполняет команду": "commands",
            "Компьютер не видит кассу": "pc",
            "ФН закрыт": "fn_closed",
            "Бамаги нет": "paper",
            "Пишет нет бумаги, хотя рулон установлен": "paper",
            "Переполнение буфера ЭЖ": "overflow",
            "Снятие отчёта прервалось": "shift",
            "Лицензия истекла вчера утром": "license",
            "Лицензия закончилась": "license",
            "На чеке пропадают точки": "dots",
            "Из кассы выходит пустая лента": "blank",
            "Зелёная горит, красная мигает": "cover",
            "Два красных, два зеленых мигания": "selftest",
            "Выключен интерфейс": "interface",
            "Принтер перегрелся": "heat",
            "Неверная дата в ФН": "date",
            "Нет транспортного соединения ФН": "fn_link",
            "ОФД не подтверждает чеки": "ofd",
            "Зажовало бумагу": "jam",
            "Не пичатает чек": "group_print",
            "Касса зависла": "group_response",
            "Ошибка 99999": "group_errors",
            "Мигает лампочка": "group_indicators",
        }
        for message, target in examples.items():
            with self.subTest(message=message):
                self.assertEqual(suggest(message), [target] if target else [])
                state = self.selected_model()
                before = deepcopy(state)
                updated, _ = advance(state, message)
                self.assertEqual(state, before)
                self.assertEqual(updated["_atol_tree"]["node"], "categories")
                self.assertNotIn("performed_checks", updated)
                self.assertNotIn("sources", updated)

    def test_ambiguous_and_unknown_text_does_not_choose_a_repair(self):
        self.assertEqual(suggest("Зажевало бумагу, кнопка не работает"), ["button", "jam"])
        for message in (
            "У меня ничего не работает", "12345", "сварить борщ", "Не печатает QR код",
            "Вики Принт не печатает", "АТОЛ 55 не печатает", "Бумага не закончилась",
            "Бумагу не зажевало", "Чек не пустой", "ОФД больше не блокирует кассу",
            "Как предотвратить замятие бумаги", "раньше бумагу зажевало, сейчас все хорошо",
        ):
            with self.subTest(message=message):
                self.assertEqual(suggest(message), [])
                state, _ = advance(self.selected_model(), message)
                self.assertEqual(choices(state)[0]["label"], "Выбрать по кнопкам")
                self.assertEqual(state["_phase"], "diagnosing")

    def test_confirm_reject_correct_and_reload(self):
        original = "Зажевало ленту"
        state, answer = advance(self.selected_model(), original)
        restored = json.loads(json.dumps(state))
        self.assertEqual(choices(restored), choices(state))
        self.assertEqual(render(restored), answer)
        confirmed, answer = advance(restored, "Да")
        self.assertEqual(confirmed["_atol_tree"]["node"], "jam")
        self.assertIn(catalog()["nodes"]["jam"]["text"], answer)
        self.assertEqual(confirmed["problem"], original)
        rejected, _ = advance(state, "Нет")
        self.assertEqual(rejected["_atol_tree"]["node"], "categories")
        self.assertNotIn("proposal", rejected["_atol_tree"])
        changed, _ = advance(state, "Программа не видит кассу")
        self.assertNotEqual(choices(state)[0]["id"], choices(changed)[0]["id"])
        changed, _ = advance(changed, choices(changed)[0]["label"])
        self.assertEqual(changed["_atol_tree"]["node"], "pc")
        self.assertEqual(changed["problem"], "Программа не видит кассу")

    def test_group_proposal_does_not_assume_missing_paper(self):
        state, _ = advance(self.selected_model(), "Не печатает, бумага есть")
        state, _ = advance(state, "да")
        self.assertEqual(state["_atol_tree"]["node"], "group_print")
        self.assertNotIn("performed_checks", state)
        self.assertNotIn("sources", state)

    def test_specialist_and_cancel_keep_description_without_diagnosis(self):
        for command, phase in (("Нужен специалист", "confirm"), ("отмена", "cancelled")):
            state, _ = advance(self.selected_model(), "Непонятно гудит")
            state, _ = advance(state, command)
            self.assertEqual(state["_phase"], phase)
            self.assertIn("Непонятно гудит", [item["answer"] for item in state["observations"]])
            self.assertEqual(choices(state), [])

    def test_routing_does_not_intercept_checks_or_model_selection(self):
        state, _ = advance(initial_state(), "Бумагу зажевало")
        self.assertEqual(state["_atol_tree"]["node"], "model")
        state = self.selected_model()
        state, _ = advance(state, "Бумага и печать")
        state, _ = advance(state, "Зажевало бумагу")
        self.assertEqual(state["_atol_tree"]["node"], "jam")
        state, _ = advance(state, "Компьютер не видит кассу")
        self.assertNotIn("proposal", state["_atol_tree"])
        self.assertEqual(state["_atol_tree"]["node"], "jam")


if __name__ == "__main__":
    unittest.main()
