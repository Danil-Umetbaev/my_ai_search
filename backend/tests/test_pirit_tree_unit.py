import unittest
from unittest.mock import AsyncMock, patch

from src.services import atol_support_tree as tree
from src.services.atol_semantic_router import advance


class PiritTreeTests(unittest.IsolatedAsyncioTestCase):
    async def test_present_paper_does_not_repeat_group_confirmation(self):
        state, _ = await self.walk(("Бумага и печать",))
        state, _ = await advance(state, "бумага не закончилась, но не печатает", [])
        self.assertEqual(state['_atol_tree']['answer_offer']['label'], 'Бумага есть, но чек не выходит')
        state, reply = await advance(state, 'Да, верно', [])
        self.assertEqual(state['_atol_tree']['node'], 'pirit_indicators')
        self.assertIn('индикатор', reply)

    async def test_rejected_jam_is_not_proposed_again(self):
        state, _ = await self.walk(('Бумага и печать',))
        state, _ = await advance(state, 'блять бамагу зажевало', [])
        self.assertEqual(state['_atol_tree']['answer_offer']['label'], 'Зажевало бумагу')
        state, _ = await advance(state, 'Нет, выбрать снова', [])
        state, _ = await advance(state, 'бумагу зажевало блять', [])
        self.assertNotEqual(state['_atol_tree'].get('answer_offer', {}).get('label'), 'Зажевало бумагу')

    async def walk(self, labels):
        state = tree.initial_state()
        for label in ("Пирит 2Ф", *labels):
            self.assertIn(label, [c["label"] for c in tree.choices(state)])
            state, reply = await advance(state, label, [], button=True)
        return state, reply

    async def test_documented_actions_resolve_the_original_problem(self):
        paths = (
            ("Бумага и печать", "Закончилась лента", "Рулон закончился"),
            ("Закрытие смены", "Не завершено закрытие смены", "Не завершено закрытие, повторите операцию"),
            ("Фискальный накопитель", "Не передаются документы в ОФД", "Режим передачи в ОФД", "Больше нуля"),
            ("Проверка кассы", "Программа не видит кассу", "Выбран виртуальный порт кассовой программы", "Статус получен"),
        )
        for path in paths:
            with self.subTest(path=path):
                state, reply = await self.walk(path)
                self.assertIn("Помогло?", reply)
                state, _ = await advance(state, "Да, помогло", [], button=True)
                self.assertEqual(state["_phase"], "resolved")
                self.assertEqual(state["performed_checks"][-1]["result"], "Да, помогло")

    async def test_replacement_keeps_original_fault_after_queue_clears(self):
        state, _ = await self.walk(("Фискальный накопитель", "Ресурс или память ФН заканчиваются",
                                    "Память ФН заполнена", "С передачей в ОФД, проверить очередь",
                                    "Есть непереданные документы", "Очередь пуста, ФН требует замены"))
        self.assertEqual(state["_phase"], "confirm")
        self.assertEqual(state["environment"], "Пирит 2Ф")
        self.assertIn("Очередь пуста", state["observations"][-1]["answer"])
        self.assertIn("память ФН", state["problem"])

    async def test_text_confirmation_and_rejection_keep_context(self):
        state, _ = await self.walk(("Бумага и печать", "Закончилась лента"))
        offered, _ = await advance(state, "в отсеке рулон есть", [])
        rejected, _ = await advance(offered, "нет", [])
        self.assertEqual(rejected["_atol_tree"]["node"], "pirit_group_0_case_0")
        accepted, _ = await advance(offered, "да", [])
        self.assertEqual(accepted["_atol_tree"]["node"], "pirit_seating")
        self.assertEqual(accepted["observations"][-1]["answer"], "в отсеке рулон есть")

    async def test_unknown_text_stays_in_current_step_and_foreign_model_is_excluded(self):
        state, _ = await self.walk(("Батарея и память", "Батарея разряжена"))
        updated, _ = await advance(state, "У АТОЛ разрядилась батарея", [])
        self.assertEqual(updated, state)
        with patch("src.services.atol_document_search.search", new_callable=AsyncMock) as search:
            search.return_value = (state, "Поиск")
            await advance(state, "Необычный звук", [], lookup=AsyncMock())
            search.assert_not_called()
