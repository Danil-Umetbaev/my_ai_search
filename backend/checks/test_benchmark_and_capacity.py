import asyncio
import unittest
import json
import tempfile
from pathlib import Path

from src.ai.test_rag import load_cases, select_cases
from src.ai.analyze_rag import analyze
from src.middleware.ai_capacity import AICapacityMiddleware
from src.schemas.chat import ChatRequest
from pydantic import ValidationError


class KnowledgeStructureTests(unittest.TestCase):
    def test_chunking_keeps_original_unicode_and_prefers_line_endings(self):
        from src.ai.chunking.token import TokenChunker
        class CharacterTokenizer:
            def __call__(self, text, **kwargs):
                return {'offset_mapping': [(i, i + 1) for i in range(len(text))]}
        chunker = TokenChunker.__new__(TokenChunker)
        chunker.tokenizer = CharacterTokenizer()
        chunker.chunk_size, chunker.chunk_overlap = 26, 4
        text = 'Сервер:\nТоваровед\nКасса:\nКонсультант КСО\n'
        chunks = chunker.split(text)
        self.assertEqual(chunks[0], 'Сервер:\nТоваровед\nКасса:\n')
        self.assertTrue(all(chunk in text for chunk in chunks))
        from src.services.rag import RAGService
        chunker.chunk_overlap = 20
        chunks = chunker.split(text)
        self.assertEqual(RAGService._join_chunks(dict(enumerate(chunks))), text)

    def test_lists_keep_whole_names_and_group_boundaries(self):
        from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
        text = ConfluenceKnowledgeSource()._clear_html(
            '<p>Сервер:</p><ul><li><p>Специалист отдела</p></li>'
            '<li><p>Товаровед</p></li></ul><p>Касса:</p>'
            '<ul><li><p>Консультант <strong>КСО</strong></p></li></ul>'
        )
        self.assertIn('- Специалист отдела\n- Товаровед', text)
        self.assertIn('- Консультант КСО', text)
        self.assertLess(text.index('Товаровед'), text.index('Касса:'))

    def test_table_keeps_setting_separate_from_its_description(self):
        from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
        text = ConfluenceKnowledgeSource()._clear_html(
            '<table><tr><th>Настройка</th><th>Описание</th></tr>'
            '<tr><td>Запрет частичного возврата</td>'
            '<td>Разрешён только полный возврат.</td></tr></table>'
        )
        self.assertIn('Настройка: Запрет частичного возврата | Описание:', text)

    def test_code_and_link_labels_survive_without_macro_metadata(self):
        from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
        text = ConfluenceKnowledgeSource()._clear_html(
            '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">xml</ac:parameter>'
            '<ac:plain-text-body><![CDATA[<URL>http://server:8090</URL>\n<Port>8090</Port>]]>'
            '</ac:plain-text-body></ac:structured-macro>'
            '<p><ac:link><ri:page ri:content-title="Длинное название"/>'
            '<ac:link-body>профиль</ac:link-body></ac:link></p>'
        )
        self.assertIn('<URL>http://server:8090</URL>\n<Port>8090</Port>', text)
        self.assertIn('профиль', text)
        self.assertNotIn('Длинное название', text)
        self.assertNotIn('xml', text)


class BenchmarkTests(unittest.TestCase):
    def test_analysis_does_not_merge_different_models(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, model in enumerate(('small', 'large')):
                path = Path(directory) / f'{index}.jsonl'
                path.write_text(json.dumps(dict(type='run', model=model)) + '\n', encoding='utf-8')
                paths.append(path)
            with self.assertRaises(ValueError):
                analyze(paths)

    def test_analysis_rejects_duplicates_and_separates_review(self):
        case = load_cases()[0]
        row = dict(type='result', **case, actual='answered', confidence=0.4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.jsonl'
            path.write_text(json.dumps(row) + '\n', encoding='utf-8')
            summary = analyze([path])
            self.assertEqual(summary['processed'], 1)
            self.assertEqual(len(summary['missing_ids']), len(load_cases()) - 1)
            self.assertEqual(summary['min_status_matched_answered'], 0.4)
            self.assertIsNone(summary['min_manually_approved_answered'])
            with self.assertRaises(ValueError):
                analyze([path, path])

    def test_stable_partial_run(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 200)
        self.assertEqual([c['id'] for c in cases], list(range(1, len(cases) + 1)))
        partial = select_cases(cases, 39, 150)
        self.assertEqual(len(partial), 112)
        self.assertEqual(partial[0]['id'], 39)
        self.assertEqual(cases[125]['expected'], 'not_found')
        self.assertIn('отпуск', cases[125]['question'])
        self.assertEqual(cases[140]['expected'], 'off_topic')
        self.assertEqual(len(select_cases(cases, release=True)), 14)

    def test_request_bounds(self):
        for message in ['', '   ', 'a' * 4001]:
            with self.assertRaises(ValidationError):
                ChatRequest(conversation_id='00000000-0000-0000-0000-000000000001', message=message)


class CapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_reject_and_recover_even_after_cancel(self):
        entered, finish = asyncio.Event(), asyncio.Event()
        async def app(scope, receive, send):
            entered.set()
            await finish.wait()
        gate = AICapacityMiddleware(app)
        gate.max_requests = 1
        scope = dict(type='http', method='POST', path='/api/v1/chat/messages')
        messages = []
        async def send(message):
            messages.append(message)
        async def receive():
            return {'type': 'http.disconnect'}
        first = asyncio.create_task(gate(scope, receive, send))
        await entered.wait()
        await gate(scope, receive, send)
        self.assertEqual(messages[0]['status'], 429)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        self.assertTrue(gate.tasks)
        finish.set()
        await asyncio.gather(*gate.tasks)
        await asyncio.sleep(0)
        self.assertFalse(gate.tasks)
        await gate(scope, receive, send)

    async def test_failure_releases_slot(self):
        async def app(scope, receive, send):
            raise RuntimeError('test')
        gate = AICapacityMiddleware(app)
        with self.assertRaises(RuntimeError):
            await gate(dict(type='http', method='POST', path='/api/v1/chat/messages'), None, None)
        self.assertFalse(gate.tasks)


class EvidenceTests(unittest.TestCase):
    def test_classifier_accepts_label_before_explanation_without_prefix_confusion(self):
        from unittest.mock import Mock
        from src.ai.llm.qwen import QwenLLMProvider
        llm = QwenLLMProvider.__new__(QwenLLMProvider)
        for raw, expected in [('VALID\n\nОбоснование: ответ подтверждён.', 'VALID'),
                              ('INVALID\nWrong operation', 'INVALID'),
                              ('OFF_TOPIC.\nCreative request', 'OFF_TOPIC'),
                              ('VALIDATION', 'VALIDATION')]:
            llm._generate_text = Mock(return_value=raw)
            self.assertEqual(llm._complete('Classify', 'Question'), expected)

    def test_named_lists_keep_their_members_in_separate_groups(self):
        from src.ai.evidence import collect_evidence
        passages = collect_evidence(
            'Документ: Стандартные роли\nСервер:\n\n- Директор\n- Товаровед\n\n'
            'Касса:\n\n- Кассир\n- Старший кассир', 'Какие кассовые роли существуют?',
        )
        cash = next(p for p in passages if p.section == 'Касса')
        self.assertIn('Старший кассир', cash.text)
        self.assertNotIn('Товаровед', cash.text)

    def test_ui_labels_missing_from_cited_text_are_rejected(self):
        from src.ai.llm.qwen import QwenLLMProvider
        self.assertEqual(QwenLLMProvider._unsupported_ui_labels(
            'Нажмите кнопку «Сохранить».', 'Заполните поля и нажмите .'), ['Сохранить'])
        self.assertEqual(QwenLLMProvider._unsupported_ui_labels(
            'Откройте вкладку «Настройки».', 'Перейдите на вкладку НАСТРОЙКИ.'), [])
        self.assertEqual(QwenLLMProvider._unsupported_ui_labels(
            "Нажмите клавишу 'ОК'.", 'Откройте окно.'), ['ОК'])

    def test_overlapping_passages_leave_room_for_another_operation(self):
        from src.ai.evidence import EvidencePassage
        from src.ai.llm.qwen import QwenLLMProvider
        first = EvidencePassage('Инструкция', 'Смена', 'Закройте смену и распечатайте отчёт.')
        duplicate = EvidencePassage('Инструкция', 'Смена', 'Закройте смену и распечатайте отчёт. Подтвердите.')
        payment = EvidencePassage('Инструкция', 'Оплата', 'Введите сумму наличных.')
        self.assertEqual(QwenLLMProvider._distinct_passages([first, duplicate, payment]), [first, payment])

    def test_table_rows_keep_their_own_condition_and_action(self):
        from src.ai.evidence import collect_evidence
        passages = collect_evidence(
            'Документ: Ошибки печати\nПричина: Истёк срок ФН | Действие: Остановить продажи.\n'
            'Причина: Нет бумаги | Действие: Заменить рулон.', 'Что делать при истечении срока ФН?',
        )
        self.assertEqual(len(passages), 2)
        self.assertIn('Остановить продажи', passages[0].text)
        self.assertNotIn('Заменить рулон', passages[0].text)

    def test_parent_section_keeps_steps_but_not_an_unrelated_operation(self):
        from src.ai.evidence import collect_evidence
        passages = collect_evidence(
            'Документ: Инструкция\n# Возврат\n\nПроверьте условия.\n\n'
            '## Действия\n\n1. Выберите товар.\n2. Подтвердите.\n\n'
            '# Закрытие смены\n\nРаспечатайте отчёт.', 'Как выполнить возврат?',
        )
        parent_passages = [p for p in passages if p.section == 'Возврат']
        self.assertTrue(any('2. Подтвердите.' in p.text for p in parent_passages))
        self.assertTrue(all('Распечатайте отчёт' not in p.text for p in parent_passages))

    def test_excerpt_gap_resets_section_without_leaking_marker_into_answer(self):
        from src.ai.evidence import collect_evidence
        passages = collect_evidence(
            'Документ: Инструкция\n# Оплата\n\nПервая часть.\n[… ]\n'
            'Раздел документа: Возврат → По чеку\n## По чеку\n\nНайдите чек.',
            'Как найти чек?',
        )
        matching = [p for p in passages if 'Найдите чек.' in p.text]
        self.assertEqual(matching[0].section, 'Возврат → По чеку')
        self.assertNotIn('Раздел документа:', matching[0].text)

    def test_product_scope_accepts_family_but_not_an_unmentioned_emulator(self):
        from src.ai.evidence import compatible_title
        self.assertTrue(compatible_title('Пирит 2Ф ◾️ Ошибка приёма данных', 'Ошибка на Пирит'))
        self.assertFalse(compatible_title('SetRetail10 ◾️ VirtualScales', 'Как настроить весы?'))
        self.assertTrue(compatible_title('SetRetail10 ◾️ VirtualScales', 'Как настроить VirtualScales?'))
        self.assertTrue(compatible_title('SetRetail10 ◾️ bank.log', 'Какой лог нужен?'))

    def test_answer_keeps_code_and_cites_only_verified_fragments(self):
        from unittest.mock import Mock
        from src.ai.evidence import EvidencePassage, serialize_evidence
        from src.ai.llm.qwen import QwenLLMProvider
        llm = QwenLLMProvider.__new__(QwenLLMProvider)
        text = 'Настройте интерфейс:\n```\nethtool -s eth0 speed 10 duplex full\n```'
        llm._generate_text = Mock(return_value=json.dumps({'answer': text, 'fragments': [2]}))
        llm._complete = Mock(return_value='VALID')
        answer = llm.generate('Как настроить интерфейс?', '', serialize_evidence([
            EvidencePassage('Другой документ', '', 'Не та операция.'),
            EvidencePassage('Нужная инструкция', '', text),
        ]))
        self.assertEqual(answer.answer, text)
        self.assertEqual(answer.source_titles, ['Нужная инструкция'])

    def test_unverified_answer_is_repaired_before_publication(self):
        from unittest.mock import Mock
        from src.ai.evidence import EvidencePassage, serialize_evidence
        from src.ai.llm.qwen import QwenLLMProvider
        llm = QwenLLMProvider.__new__(QwenLLMProvider)
        llm._generate_text = Mock(side_effect=[
            json.dumps({'answer': 'Закройте смену.', 'fragments': [1]}),
            json.dumps({'answer': 'Введите сумму наличных.', 'fragments': [2]}),
        ])
        llm._complete = Mock(side_effect=['INVALID', 'VALID'])
        result = llm.generate('Как оплатить покупку?', '', serialize_evidence([
            EvidencePassage('Смена', '', 'Закройте смену.'),
            EvidencePassage('Оплата', '', 'Введите сумму наличных.'),
        ]))
        self.assertEqual(result.answer, 'Введите сумму наличных.')
        self.assertEqual(result.source_titles, ['Оплата'])

    def test_invalid_source_ids_and_rejected_drafts_are_not_published(self):
        from unittest.mock import Mock
        from src.ai.evidence import EvidencePassage, serialize_evidence
        from src.ai.llm.qwen import QwenLLMProvider
        passages = [EvidencePassage('Инструкция', '', 'Проверьте настройку.')]
        for indices in [[True], [0], [2], [], '1']:
            self.assertIsNone(QwenLLMProvider._parse_answer(
                json.dumps({'answer': 'Ответ', 'fragments': indices}), passages,
            ))
        llm = QwenLLMProvider.__new__(QwenLLMProvider)
        llm._generate_text = Mock(return_value=json.dumps({'answer': 'Выдуманный шаг.', 'fragments': [1]}))
        llm._complete = Mock(return_value='INVALID')
        result = llm.generate('Что делать?', '', serialize_evidence(passages))
        self.assertFalse(result.answerable)
        self.assertIsNone(result.answer)

    def test_local_fact_classification_requires_confirmation(self):
        from unittest.mock import Mock
        from src.ai.llm.qwen import QwenLLMProvider
        llm = QwenLLMProvider.__new__(QwenLLMProvider)
        llm._complete = Mock(side_effect=['LOCAL_FACT', 'DOCUMENTATION'])
        question = 'Какой журнал содержит обмен с терминалом?'
        self.assertEqual(llm.rewrite_query(question), question)
        llm._complete = Mock(side_effect=['LOCAL_FACT', 'OBSERVED'])
        self.assertEqual(llm.rewrite_query('Какой пароль установлен на нашей кассе?'), 'NOT_FOUND')


class RAGContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_unrelated_plugin_does_not_raise_relative_cutoff_for_manual(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock
        from uuid import uuid4
        from src.services.rag import RAGService
        from src.schemas.llm import LLMAnswerSchema
        def chunk(title):
            return SimpleNamespace(document_id=uuid4(), chunk_id=uuid4(), chunk_index=0,
                                   document_title=title, document_url='https://example.test/manual',
                                   content='Откройте меню возврата.')
        plugin = chunk('Беларусь ◾️ eBridge')
        manual = chunk('SetRetail10 ◾️ Руководство пользователя')
        db = Mock(document_chunks=Mock(search_lexical=AsyncMock(return_value=[]),
                                       get_neigbors=AsyncMock(return_value=[])),
                  documents=Mock(get_one=AsyncMock(return_value=SimpleNamespace(
                      title=manual.document_title, content=manual.content))))
        llm = Mock()
        llm.rewrite_query.return_value = 'Как оформить возврат?'
        llm.generate.return_value = LLMAnswerSchema(answerable=True, answer=manual.content,
                                                    source_titles=[manual.document_title])
        reranker = Mock(rerank=Mock(side_effect=[[.99, .1], [.1]]))
        result = await RAGService(db, Mock(search=AsyncMock(return_value=[plugin, manual])),
                                  llm, reranker).answer('Как оформить возврат?')
        self.assertEqual(result.confidence, .1)
        self.assertEqual([source.document_id for source in result.sources], [manual.document_id])
        self.assertNotIn('eBridge', llm.generate.call_args.args[2])

    async def test_live_unknown_value_is_not_searched_as_a_literal_marker(self):
        from unittest.mock import AsyncMock, Mock
        from src.services.rag import RAGService
        from src.schemas.rag import RAGStatus
        llm = Mock(rewrite_query=Mock(return_value='NOT_FOUND'))
        search = Mock(search=AsyncMock())
        result = await RAGService(Mock(), search, llm, Mock()).answer('Какой IP назначен нашей кассе?')
        self.assertEqual(result.status, RAGStatus.NOT_FOUND)
        search.search.assert_not_awaited()

    def test_definition_lookup_extracts_and_escapes_term_only(self):
        from src.services.rag import RAGService
        import re
        self.assertIn(re.escape('мягкий чек'), RAGService._definition_pattern('Что такое мягкий чек?'))
        pattern = RAGService._definition_pattern('Что означает термин «A+B»?')
        self.assertIn(re.escape('A+B'), pattern)
        self.assertNotIn('SetRetail10', RAGService._definition_pattern('Что такое PLU в SetRetail10?'))
        self.assertIsNone(RAGService._definition_pattern('Как оплатить чек?'))

    def test_context_keeps_other_relevant_passages_in_selected_manual(self):
        from types import SimpleNamespace
        from src.services.rag import RAGService
        ranked = [(SimpleNamespace(document_id=doc, chunk_id=i), score)
                  for i, (doc, score) in enumerate([
                      ('manual', .95), ('manual', .9), ('other', .85),
                      ('manual', .8), ('manual', .75), ('unselected', .7)])]
        selected = RAGService._select_chunks(ranked, 2)
        expanded = RAGService._extend_context_chunks(selected, ranked)
        self.assertEqual({chunk.chunk_id for chunk, _ in expanded}, {0, 1, 2, 3})
        self.assertEqual(len(expanded), 4)
        self.assertEqual(expanded[:2], selected)

    def test_context_selection_does_not_crowd_out_other_documents(self):
        from types import SimpleNamespace
        from src.services.rag import RAGService
        ranked = [(SimpleNamespace(document_id=doc, chunk_id=i), score)
                  for i, (doc, score) in enumerate([('emulator', .95), ('emulator', .94),
                                                  ('emulator', .93), ('manual', .9), ('setup', .8)])]
        selected = RAGService._select_chunks(ranked, 3)
        self.assertEqual([chunk.document_id for chunk, _ in selected], ['emulator', 'manual', 'setup'])
        selected = RAGService._select_chunks(ranked[:3], 3)
        self.assertEqual(len(selected), 3)
        self.assertEqual(len({chunk.chunk_id for chunk, _ in selected}), 3)

    async def test_off_topic_skips_search_and_generation(self):
        from unittest.mock import AsyncMock, Mock
        from src.services.rag import RAGService
        from src.schemas.rag import RAGStatus
        llm = Mock()
        llm.rewrite_query.return_value = 'OFF_TOPIC'
        search = Mock(search=AsyncMock())
        result = await RAGService(Mock(), search, llm, Mock()).answer('Расскажи анекдот')
        self.assertEqual(result.status, RAGStatus.OFF_TOPIC)
        search.search.assert_not_awaited()
        llm.generate.assert_not_called()

    async def test_empty_search_returns_not_found_without_generation(self):
        from unittest.mock import AsyncMock, Mock
        from src.services.rag import RAGService
        from src.schemas.rag import RAGStatus
        question = 'Как оформить отпуск?'
        llm = Mock()
        llm.rewrite_query.return_value = question
        db = Mock(document_chunks=Mock(search_lexical=AsyncMock(return_value=[])))
        search = Mock(search=AsyncMock(return_value=[]))
        result = await RAGService(db, search, llm, Mock()).answer(question)
        self.assertEqual(result.status, RAGStatus.NOT_FOUND)
        llm.generate.assert_not_called()

    def test_context_overlap_preserves_complete_text_and_gaps(self):
        from src.services.rag import RAGService
        overlap = 'совпадающий фрагмент исходного документа'
        self.assertEqual(RAGService._join_chunks({1: 'Начало ' + overlap, 2: overlap + ' конец'}),
                         'Начало ' + overlap + ' конец')
        self.assertIn('[… ]', RAGService._join_chunks({1: overlap, 3: overlap}))

    def test_excerpt_preserves_example_scope_and_complete_condition(self):
        from src.services.rag import RAGService
        content = '# Настройка\n\nОбщие параметры.\n\n# Пример\n\n## Клавиатурная касса\n\nЕсли сумма больше 300, применяется скидка 15%.\n'
        result = RAGService._context_excerpt(content, {12: 'сумма больше 300, применяется скидка'})
        self.assertIn('Раздел документа: Пример → Клавиатурная касса', result)
        self.assertIn('Если сумма больше 300, применяется скидка 15%.', result)
        self.assertNotIn('Общие параметры', result)

    def test_excerpt_does_not_guess_location_of_repeated_text(self):
        from src.services.rag import RAGService
        text = 'Повторяющаяся строка инструкции.'
        content = '# Один\n' + text + '\n# Два\n' + text
        self.assertEqual(RAGService._context_excerpt(content, {7: text}), text)

    def test_repeated_boilerplate_does_not_discard_unique_section_scope(self):
        from src.services.rag import RAGService
        repeated = 'Нажмите кнопку подтверждения.'
        content = '# Продажа\n\n' + repeated + '\n\n# Возврат\n\nВозвращается часть веса.\n\n' + repeated
        result = RAGService._context_excerpt(content, {7: 'Возвращается часть веса.', 8: repeated})
        self.assertIn('Раздел документа: Возврат', result)
        self.assertIn('Возвращается часть веса.', result)
        self.assertNotIn('Раздел документа: Продажа', result)

    def test_excerpt_preserves_new_heading_inside_selected_range(self):
        from src.services.rag import RAGService
        content = '# Пример\nТест.\n# Решение\nВыполните проверку.\n'
        result = RAGService._context_excerpt(content, {2: '# Решение\nВыполните проверку.'})
        self.assertIn('# Решение', result)
        self.assertIn('Выполните проверку.', result)
        self.assertNotIn('Раздел документа: Пример\n# Решение', result)

    def test_long_excerpt_keeps_bounded_introduction_before_example(self):
        from src.services.rag import RAGService
        content = '# Описание\n\nРазмер скидки задаётся настройками акции.\n\n# Настройка\n\n' + 'Детали. ' * 200 + '\n\n# Пример\n\nВ примере скидка 15%.\n'
        result = RAGService._context_excerpt(content, {20: 'В примере скидка 15%.'})
        self.assertIn('Размер скидки задаётся настройками акции.', result)
        self.assertIn('Раздел документа: Пример', result)
        self.assertLess(len(result), 400)

    def test_overview_keeps_complete_heading_catalog_without_unrelated_sections(self):
        from src.services.rag import RAGService
        anchor = 'Настройте время действия.'
        content = ('# Условия\n\n' + 'Описание условий. ' * 300
                   + '\n\n## По времени\n\n' + anchor
                   + '\n\n## По клиенту\n\nПроверьте карту.'
                   + '\n\n## По товару\n\nВыберите товары.'
                   + '\n\n# Другая операция\n\n## Закрытие смены\n\nЗакройте смену.')
        excerpt = RAGService._context_excerpt(content, {4: anchor}, [anchor], overview=True)
        self.assertIn('Подразделы документации:', excerpt)
        for label in ('По времени', 'По клиенту', 'По товару'):
            self.assertIn('- ' + label, excerpt)
        self.assertNotIn('Закрытие смены', excerpt)
        ordinary = RAGService._context_excerpt(content, {4: anchor}, [anchor])
        self.assertNotIn('Подразделы документации:', ordinary)

    async def test_short_instruction_includes_solution_outside_retrieved_window(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock
        from uuid import uuid4
        from src.services.rag import RAGService
        from src.schemas.llm import LLMAnswerSchema
        chunk = SimpleNamespace(document_id=uuid4(), chunk_id=uuid4(), chunk_index=0,
                                document_title='Инструкция', document_url='https://example.test/instruction',
                                content='Описание сбоя.')
        full_text = 'Описание сбоя. Решение: обратиться к инженеру банка.'
        db = Mock(document_chunks=Mock(search_lexical=AsyncMock(return_value=[]),
                                       get_neigbors=AsyncMock(return_value=[chunk])),
                  documents=Mock(get_one=AsyncMock(return_value=SimpleNamespace(title='Инструкция', content=full_text))))
        llm = Mock()
        llm.rewrite_query.return_value = 'Кто исправляет сбой?'
        llm.generate.return_value = LLMAnswerSchema(answerable=True, answer='Инженер банка.', source_titles=['Инструкция'])
        reranker = Mock()
        reranker.rerank.return_value = [.9]
        result = await RAGService(db, Mock(search=AsyncMock(return_value=[chunk])), llm, reranker).answer('Кто исправляет сбой?')
        self.assertIn(full_text, llm.generate.call_args.args[2])
        self.assertEqual([source.title for source in result.sources], ['Инструкция'])
        self.assertEqual(result.used_chunks[0].chunk_id, chunk.chunk_id)

    def test_arithmetic_does_not_reject_working_questions_with_numbers(self):
        from src.ai.llm.base import is_arithmetic_question
        for question in ['Сколько будет 27 умножить на 43?', 'Сколько будет два умножить на два?', '2 + 2']:
            self.assertTrue(is_arithmetic_question(question))
        for question in ['Как продать 2 товара по цене 100 рублей?', 'Сколько будет стоить касса?', 'Ошибка 2 на кассе 2', 'Как вернуть 2 товара?']:
            self.assertFalse(is_arithmetic_question(question))

    def test_benchmark_includes_incidents_with_evidence_and_all_statuses(self):
        cases = load_cases()
        incidents = [c for c in cases if c.get('category') == 'incident']
        self.assertGreaterEqual(len(incidents), 40)
        self.assertTrue(all(c.get('required_facts') and c.get('reference_sources') for c in incidents))
        self.assertEqual({c['expected'] for c in cases}, {'answered', 'off_topic', 'not_found'})


if __name__ == '__main__':
    unittest.main()
