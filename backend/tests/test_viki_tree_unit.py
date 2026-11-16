import unittest

from src.services import atol_support_tree as tree
from src.services.atol_semantic_router import advance


class VikiTreeTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_offer_reload_rejection_and_result(self):
        state, _ = await advance(tree.initial_state(), "у нас Viki Print 57", [])
        state, _ = await advance(state, "Да, верно", [], button=True)
        self.assertEqual(state["environment"], "Вики Принт")
        self.assertEqual(len(tree.choices(state)), 6)
        state, _ = await advance(state, "горит красный индикатор", [])
        state, _ = await advance(state, "Нет, выбрать снова", [], button=True)
        self.assertEqual(state["_atol_tree"]["node"], "viki_categories")
        state, _ = await advance(state, "принтер недоступен", [])
        state, _ = await advance(state, "да", [])
        state, _ = await advance(state, "диагностический чек напечатался", [])
        state, reply = await advance(state, "да", [])
        self.assertIn("Помогло?", reply)
        self.assertIn("кабель", reply)
        state, _ = await advance(state, "Не помогло", [], button=True)
        self.assertEqual(state["_atol_tree"]["node"], "viki_ports")
        for answer in ("Порт виден без предупреждения", "ComProxy", "Не помогло",
                       "Fito соединяется, кассовая программа нет"):
            state, _ = await advance(state, answer, [], button=True)
        self.assertEqual(state["_phase"], "confirm")
        self.assertEqual(state["observations"][-1]["answer"], answer)
        self.assertEqual(state["check_result"], "Не помогло")
        self.assertEqual(state["environment"], "Вики Принт")

    async def test_paper_qr_and_ofd_can_be_resolved(self):
        for path in (
            ("Бумага и протяжка", "Зажевало ленту", "Удалось освободить ленту", "Лента выходит ровно"),
            ("Что напечатано на чеке", "На чеке нет QR-кода", "Фискальный чек читается, только QR отсутствует"),
            ("Передача чеков в ОФД", "Чеки не доходят до ОФД", "Тариф действует",
             "Сайт открывается", "Служба установлена, но остановлена"),
            ("Ошибки смены и ФН", "Разница во времени при регистрации", "Время на ПК неверное"),
        ):
            with self.subTest(path=path):
                state = tree.initial_state()
                for answer in ("Вики Принт", *path, "Да, помогло"):
                    self.assertIn(answer, [item["label"] for item in tree.choices(state)])
                    state, _ = await advance(state, answer, [], button=True)
                self.assertEqual(state["_phase"], "resolved")
                self.assertTrue(state["performed_checks"])

    async def test_other_family_cannot_select_viki_symptom(self):
        state, _ = await advance(tree.initial_state(), "Вики Принт", [], button=True)
        updated, _ = await advance(state, "У Пирит закончилась бумага", [])
        self.assertEqual(state, updated)
