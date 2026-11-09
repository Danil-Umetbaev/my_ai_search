"""Reviewed source explanations, kept separate from executable procedures."""

import json
import re
from functools import lru_cache

from src.services.equipment_scope import document_matches
from src.services.receipt_procedures import DATA, catalog, condition_matches


@lru_cache(maxsize=1)
def reference_notes():
    return json.loads(
        (DATA / "receipt_reference_notes.json").read_text(encoding="utf-8")
    )["notes"]


def select_reference(query, facts, preferred=False):
    for note in reference_notes():
        if note["prefer_reference"] != preferred:
            continue
        if not all(condition_matches(facts, rule) for rule in note["conditions"]):
            continue
        pattern = note.get("query_pattern")
        if pattern and not re.search(pattern, query, re.I):
            continue
        excluded = note.get("exclude_query_pattern")
        if excluded and re.search(excluded, query, re.I):
            continue
        return note
    return None


def explain_reference(note, documents, facts):
    sources = catalog()["sources"]
    current = {str(doc["id"]): doc for doc in documents if not doc.get("is_archived")}
    links = []
    for ref in note["source_refs"]:
        source = sources[ref]
        document = current.get(source["document_id"])
        if not document or document["checksum"] != source["checksum"]:
            return None
        # A note must not broaden the source's equipment applicability.
        if not document_matches(document, facts):
            return None
        links.append({"title": source["title"], "url": source["url"]})
    return {
        "status": "answered",
        "kind": "information",
        "reference_id": note["id"],
        "answer": note["answer"],
        "reason": note["limitation"],
        "sources": links,
    }
