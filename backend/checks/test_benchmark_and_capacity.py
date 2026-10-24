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


class RAGContractTests(unittest.IsolatedAsyncioTestCase):
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

    def test_excerpt_preserves_new_heading_inside_selected_range(self):
        from src.services.rag import RAGService
        content = '# Пример\nТест.\n# Решение\nВыполните проверку.\n'
        result = RAGService._context_excerpt(content, {2: '# Решение\nВыполните проверку.'})
        self.assertIn('# Решение', result)
        self.assertIn('Выполните проверку.', result)
        self.assertNotIn('Раздел документа: Пример', result)

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
