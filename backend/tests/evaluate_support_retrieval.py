"""Evaluate the actual retrieval payload without loading or invoking an LLM."""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

from src.services.equipment_scope import document_matches
from src.services.receipt_procedures import DATA, catalog, render_procedure
from src.services.support_retrieval import retrieve_materials


def evaluate(documents):
    cases = json.loads(
        (DATA / "receipt_retrieval_cases.json").read_text(encoding="utf-8")
    )["cases"]
    by_id = {str(doc["id"]): doc for doc in documents}
    hits = Counter()
    failures = []
    started = perf_counter()
    for case in cases:
        source = by_id.get(case["expected_document_id"])
        if not source or source["checksum"] != case["source_checksum"]:
            raise AssertionError(
                f"{case['id']}: source missing or changed; review the reference"
            )
        for fragment in case["required_fragments"]:
            if fragment.casefold() not in source["content"].casefold():
                raise AssertionError(
                    f"{case['id']}: reference fragment missing: {fragment}"
                )
        payload = retrieve_materials(documents, case["question"], case["facts"])
        for item in payload:
            if not document_matches(by_id[item["document_id"]], case["facts"]):
                raise AssertionError(
                    f"{case['id']}: wrong equipment in downstream payload"
                )
            if item["text"] != by_id[item["document_id"]]["content"]:
                raise AssertionError(
                    f"{case['id']}: source restrictions were truncated"
                )
        found = next(
            (
                item
                for item in payload
                if item["document_id"] == case["expected_document_id"]
            ),
            None,
        )
        success = found and all(
            fragment.casefold() in found["text"].casefold()
            for fragment in case["required_fragments"]
        )
        if success:
            hits[case["facts"]["model"]] += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "expected": case["source_ref"],
                    "retrieved": [item["title"] for item in payload],
                }
            )
    rendering = []
    for procedure in catalog()["procedures"]:
        result = render_procedure(procedure, documents)
        expected = "answered" if procedure["status"] == "ready" else "blocked"
        if result["status"] != expected:
            rendering.append({"id": procedure["id"], "result": result})
    report = {
        "documents": len(documents),
        "cases": len(cases),
        "found": sum(hits.values()),
        "recall_at_5": sum(hits.values()) / len(cases),
        "by_model": dict(hits),
        "seconds": round(perf_counter() - started, 3),
        "failures": failures,
        "procedure_source_failures": rendering,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return not failures and not rendering


async def read_database():
    from src.database import async_session_maker, engine
    from src.repositories.documents import DocumentRepository

    try:
        async with async_session_maker() as session:
            return await DocumentRepository(session).get_support_documents()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Optional offline corpus; otherwise read the configured database",
    )
    args = parser.parse_args()
    documents = (
        json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
        if args.snapshot
        else asyncio.run(read_database())
    )
    raise SystemExit(0 if evaluate(documents) else 1)
