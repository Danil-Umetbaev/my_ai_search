"""Merge disjoint JSONL runs; never silently count duplicate case IDs."""
import argparse
import json
import math
import statistics
from pathlib import Path

from src.ai.test_rag import load_cases


def analyze(paths):
    expected = {c['id']: c for c in load_cases()}
    results = {}
    runs = []
    for path in paths:
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['type'] == 'run':
                runs.append(row)
            if row['type'] != 'result':
                continue
            case_id = row['id']
            if case_id in results:
                raise ValueError(f'Duplicate case {case_id}: choose disjoint runs')
            if case_id not in expected or any(row[k] != expected[case_id][k]
                                              for k in ('question', 'expected')):
                raise ValueError(f'Dataset mismatch for case {case_id}')
            results[case_id] = row
    signatures = {tuple(r.get(k) for k in ('dataset_sha256', 'label', 'threshold',
                                           'candidate_k', 'lexical_k', 'top_k')) for r in runs}
    if len(signatures) > 1:
        raise ValueError('Mixed dataset/configuration/labels; analyze runs separately')
    errors = [r['id'] for r in results.values() if 'error' in r]
    failures = [dict(id=r['id'], question=r['question'], expected=r['expected'],
                     actual=r.get('actual'), confidence=r.get('confidence'))
                for r in results.values() if 'error' not in r and r.get('actual') != r['expected']]
    answered = [r['confidence'] for r in results.values()
                if r.get('actual') == r['expected'] == 'answered' and r.get('confidence') is not None]
    reviewed = [r['confidence'] for r in results.values()
                if r.get('actual') == 'answered' and r.get('confidence') is not None
                and all(r.get('review', {}).get(k) is True
                        for k in ('answer_correct', 'source_correct', 'complete'))]
    durations = sorted(r['duration_seconds'] for r in results.values()
                       if 'error' not in r and isinstance(r.get('duration_seconds'), (int, float)))
    confusion = {}
    for row in results.values():
        bucket = confusion.setdefault(row['expected'], {})
        actual = row.get('actual', 'error')
        bucket[actual] = bucket.get(actual, 0) + 1
    reviewed_results = [r for r in results.values() if r.get('actual') == 'answered'
                        and all(isinstance(r.get('review', {}).get(k), bool)
                                for k in ('answer_correct', 'source_correct', 'complete'))]
    quality_failures = [r['id'] for r in reviewed_results
                        if not all(r['review'][k] for k in ('answer_correct', 'source_correct', 'complete'))]
    return dict(confusion_matrix=confusion,
                latency_seconds=dict(median=statistics.median(durations) if durations else None,
                                     p95=durations[math.ceil(len(durations) * .95) - 1] if durations else None,
                                     maximum=max(durations, default=None)),
                reviewed_answers=len(reviewed_results), quality_failure_ids=quality_failures,
                processed=len(results), missing_ids=sorted(expected.keys() - results.keys()),
                status_correct=len(results)-len(errors)-len(failures),
                failures=failures, error_ids=errors,
                min_status_matched_answered=min(answered, default=None),
                manually_approved_answers=len(reviewed),
                min_manually_approved_answered=min(reviewed, default=None))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps(analyze(args.files), ensure_ascii=False, indent=2))
