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


if __name__ == '__main__':
    unittest.main()
