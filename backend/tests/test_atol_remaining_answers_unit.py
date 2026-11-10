import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.services import atol_support_tree as tree
from src.services.atol_semantic_router import advance
from src.services.atol_answer_validation import policy
import test_atol_tree_unit as tree_tests


RESULTS = ["Теперь все заработало", "Проверил, все равно не работает", "Не могу выполнить эти действия"]
CONSENT = ["Давайте позовем специалиста"]
CASES = {
    "button": ["Сейчас выполняется операция", "Бумагу зажевало", "Не знаю что происходит"],
    "wait": RESULTS, "date_lock": RESULTS, "fn": CONSENT, "fn_closed": CONSENT,
    "ofd_lock": ["Передает через компьютер", "Не знаю какой канал"],
    "ofd_settings": ["Как провести тест связи", "ОФД получил все документы", "Подтверждения от ОФД нет", "Не знаю адрес и порт"],
    "commands": ["Пишет смена больше 24 часов", "Просит ввести дату", "Пишет операция не завершена", "Пишет нет ФН", "Не могу прочитать сообщение"],
    "shift24": RESULTS, "unfinished": ["Операция продажи прервалась при отключении питания"],
    "pc": ["Покажи как проверить связь", "Программа увидела кассу", "Программа не видит кассу", "Нет доступа к программе"],
    "overflow": RESULTS, "shift": RESULTS,
    "license": ["В сообщении написано название лицензии: тестовая лицензия"],
    "cover": ["Красный индикатор перестал мигать", "Индикатор все еще мигает", "Не могу закрыть крышку"],
    "selftest": ["Ошибка заводского номера", "В отчете ошибка ФН", "ФН от другой кассы написано", "Требуется замена ФН", "Не могу прочитать отчет"],
    "serial": CONSENT, "wrong_fn": CONSENT, "fn_link": CONSENT,
    "interface": ["Пишет вайфай", "Написано Ethernet", "Речь о модеме GSM", "Не могу прочитать канал"],
    "interface_help": ["Покажи настройки канала", "Давайте позовем специалиста"],
    "date": RESULTS,
    "ofd": ["Подтверждение от ОФД получено", "Разбудил компьютер, подтверждения нет", "Не могу выполнить эти действия"],
    "pc_details": ["Связь с кассой установлена", "Связи с кассой нет", "Не знаю где программа"],
    "ofd_diagnostics": ["Тест успешный, подключение есть, непереданных документов 17"],
    "interface_details": ["Канал включился, ошибка исчезла", "Ошибка осталась, канал выключен", "Нет доступа к настройкам"],
}


class RemainingAnswerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.states = tree_tests.AtolTreeTests().states()

    async def test_all_new_choices_match_button_paths(self):
        for node, messages in CASES.items():
            for index, message in enumerate(messages):
                with self.subTest(node=node, message=message):
                    state = self.states[node]
                    label = tree.catalog()["nodes"][node]["choices"][index]["label"]
                    model = SimpleNamespace(route_support=Mock(return_value=json.dumps({"question": node, "choice": label})))
                    expected, answer = tree.advance(state, label)
                    actual, text = await advance(state, message, [], model)
                    self.assertEqual(actual["_atol_tree"]["node"], expected["_atol_tree"]["node"])
                    self.assertEqual(text, answer)
                    self.assertEqual(actual.get("performed_checks"), expected.get("performed_checks"))
                    if tree.catalog()["nodes"][node]["kind"] == "input":
                        self.assertEqual(actual["additional_context"], message)
                        model.route_support.assert_not_called()

    async def test_partial_observations_do_not_prove_success(self):
        for node, message, label in (
            ("pc", "Кабель подключен", "Да, помогло"),
            ("ofd_lock", "Подключен кабель", "Через компьютер (EthernetOverTransport)"),
            ("ofd_settings", "Тест успешный, связь есть", "Да, помогло"),
            ("ofd", "Тест успешный, непереданных документов 12", "Да, помогло"),
            ("interface", "По проводу", "Ethernet"),
            ("button", "Касса зависла", "Выполняет операцию"),
        ):
            model = SimpleNamespace(route_support=Mock(return_value=json.dumps({"question": node, "choice": label})))
            state = self.states[node]
            updated, _ = await advance(state, message, [], model)
            self.assertEqual(updated["_atol_tree"], state["_atol_tree"], (node, message))

    async def test_condition_correction_updates_only_relevant_facts(self):
        state = self.states["interface"]
        state, _ = tree.advance(state, "Wi-Fi")
        state, _ = tree.advance(state, "Показать настройки канала")
        model = SimpleNamespace(route_support=Mock(return_value='{"question":"interface","choice":"Ethernet"}'))
        updated, _ = await advance(state, "Ошибся, написано Ethernet, не Wi-Fi", [], model)
        self.assertEqual(updated["_atol_tree"]["node"], "interface_help")
        self.assertEqual(updated["diagnostic_facts"]["Выключенный интерфейс"], "Ethernet")
        self.assertEqual(state["diagnostic_facts"]["Выключенный интерфейс"], "Wi-Fi")
        self.assertNotIn("paper_facts", updated)

    async def test_explicit_negative_result_overrides_an_incorrect_model_guess(self):
        for node, message, target in (
            ("pc", "Программа не видит кассу", "handoff"),
            ("pc_details", "Связи с кассой нет", "handoff"),
            ("ofd_settings", "Подтверждения от ОФД нет", "handoff"),
            ("ofd", "Разбудил компьютер, подтверждения нет", "ofd_lock"),
        ):
            model = SimpleNamespace(route_support=Mock(return_value=json.dumps({"question": node, "choice": "Да, помогло"})))
            updated, _ = await advance(self.states[node], message, [], model)
            self.assertEqual(updated["_atol_tree"]["node"], target)
            self.assertEqual(updated["check_result"], "Не помогло")
            model.route_support.assert_not_called()

    def test_inheritance_does_not_mutate_shared_policies(self):
        first = policy("pc_details")
        first["evidence"]["0"].append("injected")
        self.assertNotIn("injected", policy("pc_details")["evidence"]["0"])
        self.assertNotIn("injected", policy("date")["evidence"]["0"])


if __name__ == "__main__":
    unittest.main()
