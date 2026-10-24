"""Stable benchmark: python -m src.ai.test_rag --help."""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CASES_PATH = Path(__file__).with_name('benchmark_cases.json')
RELEASE_IDS = {16, 17, 23, 55, 94, 111, 125, 126, 130, 134, 141, 144, 147, 150}


def load_cases(path=CASES_PATH):
    cases = json.loads(path.read_text(encoding='utf-8'))
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs')
    for case in cases:
        if case['expected'] not in {'answered', 'not_found', 'off_topic'}:
            raise ValueError(f"Invalid expected status: {case['id']}")
    return cases


def select_cases(cases, start=1, end=None, release=False):
    if end is None:
        end = max(c['id'] for c in cases)
    if start < 1 or end < start:
        raise ValueError('Use 1 <= start <= end')
    selected = [c for c in cases if start <= c['id'] <= end
                and (not release or c['id'] in RELEASE_IDS)]
    if not selected:
        raise ValueError('No cases selected')
    return selected


async def run(args, cases):
    from src.ai.embeddings.qwen import QwenEmbeddingProvider
    from src.ai.llm.qwen import QwenLLMProvider
    from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider
    from src.database import async_session_maker
    from src.services.rag import RAGService
    from src.services.vector_search import VectorSearchService
    from src.utils.db import DBManager

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        metadata = dict(type='run', started_at=datetime.now(timezone.utc).isoformat(),
                        label=args.label, selected_ids=[c['id'] for c in cases],
                        dataset_sha256=hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
                        threshold=0.30, candidate_k=40, lexical_k=20, top_k=3)
        output.write(json.dumps(metadata, ensure_ascii=False) + '\n')
        output.flush()
        async with DBManager(async_session_maker) as db:
            embedding = QwenEmbeddingProvider()
            rag = RAGService(db, VectorSearchService(db, embedding),
                             QwenLLMProvider(), CrossEncoderRerankerProvider())
            correct = failures = errors = 0
            for case in cases:
                started = time.monotonic()
                record = dict(type='result', **case)
                try:
                    result = await rag.answer(case['question'], threshold=0.30,
                                              candidate_k=40, lexical_k=20, top_k=3)
                    record.update(result.model_dump(mode='json'))
                    record['actual'] = result.status.value
                    record['status_correct'] = record['actual'] == case['expected']
                    record['review'] = dict(answer_correct=None, source_correct=None,
                                            complete=None, notes='')
                    if record['status_correct']:
                        correct += 1
                    else:
                        failures += 1
                except Exception as error:
                    errors += 1
                    record['error'] = f'{type(error).__name__}: {error}'
                    await db.rollback()
                record['duration_seconds'] = round(time.monotonic() - started, 3)
                output.write(json.dumps(record, ensure_ascii=False) + '\n')
                output.flush()
                mark = 'ERROR' if 'error' in record else 'OK' if record['status_correct'] else 'FAIL'
                print(f"[{case['id']:03}/{max(c['id'] for c in load_cases())}] {mark} expected={case['expected']} "
                      f"actual={record.get('actual', '-')} confidence={record.get('confidence')}", flush=True)
            summary = dict(type='summary', processed=len(cases), correct=correct,
                           failures=failures, errors=errors)
            output.write(json.dumps(summary) + '\n')
            print(json.dumps(summary))
            return 1 if failures or errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, default=1, help='First case ID, inclusive')
    parser.add_argument('--end', type=int, default=None, help='Last case ID, inclusive; default: all cases')
    parser.add_argument('--release', action='store_true', help='14 boundary/regression cases')
    parser.add_argument('--list', action='store_true', help='List cases without AI')
    parser.add_argument('--label', default='', help='Commit/configuration identifier')
    parser.add_argument('--output', type=Path, default=Path('test_output') / (
        'rag-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.jsonl'))
    args = parser.parse_args()
    cases = select_cases(load_cases(), args.start, args.end, args.release)
    if args.list:
        print(json.dumps(cases, ensure_ascii=False, indent=2))
        return 0
    return asyncio.run(run(args, cases))


if __name__ == '__main__':
    sys.exit(main())
