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
