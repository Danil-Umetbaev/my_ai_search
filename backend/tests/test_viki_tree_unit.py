import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import AsyncMock

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
                       "Fito соединяется, кассовая программа нет", "Другая программа или не знаю"):
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

    async def test_negations_cannot_be_overridden_by_model(self):
        for node, message, wrong in (
            ('viki_ofd_service', 'Служба не работает', 'Одна служба работает'),
            ('viki_network', 'Сайт не открывается, блять', 'Сайт открывается'),
            ('pirit_categories', 'Бумага не закончилась, но не печатает', 'Закончилась лента'),
            ('viki_categories', 'Бумага не закончилась', 'Бумага закончилась'),
        ):
            state = tree.initial_state()
            state['_atol_tree']['node'] = node
            model = SimpleNamespace(route_support=Mock(return_value=json.dumps({'choice': wrong})))
            updated, _ = await advance(state, message, [], model)
            self.assertNotEqual(updated['_atol_tree'].get('answer_offer', {}).get('label'), wrong)

    async def test_vague_complaint_does_not_invent_symptom(self):
        for node in ('viki_categories', 'pirit_categories'):
            state = tree.initial_state()
            state['_atol_tree']['node'] = node
            model = SimpleNamespace(route_support=Mock())
            updated, reply = await advance(state, 'касса ебать ничего не работает', [], model)
            self.assertEqual(updated, state)
            self.assertIn('Что именно', reply)
            model.route_support.assert_not_called()

    async def test_unclear_check_result_does_not_escalate_through_search(self):
        state = tree.initial_state()
        state['_atol_tree']['node'] = 'viki_ofd_service'
        lookup = AsyncMock()
        model = SimpleNamespace(route_support=Mock(return_value='{"choice":null}'))
        updated, reply = await advance(state, 'Служба не работает', [], model, lookup=lookup)
        self.assertEqual(updated, state)
        self.assertIn('Уточните', reply)
        lookup.assert_not_called()

    async def test_documented_continuations_before_handoff(self):
        cases = (
            ('pirit_ofd_send', ['Не помогло', 'Да, помогло']),
            ('viki_ofd_queue', ['Число не меняется и новых документов нет', 'Да, показать шаги', 'Да, помогло']),
            ('viki_connection_result', ['Fito соединяется, кассовая программа нет', 'Дримкас Старт', 'Да, помогло']),
            ('viki_connection_result', ['Fito соединяется, кассовая программа нет', 'Вики Микро', 'Не могу выполнить']),
        )
        for node, answers in cases:
            state = tree.initial_state()
            state['_atol_tree']['node'] = node
            for answer in answers:
                self.assertIn(answer, [c['label'] for c in tree.choices(state)])
                state, _ = await advance(state, answer, [], button=True)
            self.assertEqual(state['_phase'], 'confirm' if answers[-1] == 'Не могу выполнить' else 'resolved')
