"""CPU retrieval over complete, model-compatible source sections; no generation."""

import math
import re
from collections import Counter

from src.services.equipment_scope import document_matches

STOP_WORDS = set(
    "как какой какая какие что где почему можно нужно надо для при после это меня мне пожалуйста касса кассе ккт принт вики пирит атол fprint модель инструкция сведения проблема есть нет работе через если или чтобы делать значит означает".split()
)


def terms(text):
    text = re.sub(r"не реаг\w*", "нет реакции", text, flags=re.I)
    words = re.findall(r"[a-zа-яё0-9]+", text.casefold().replace("ё", "е"))
    return [
        word[:5] if re.fullmatch(r"[а-я]{6,}", word) else word
        for word in words
        if len(word) >= 3 and word not in STOP_WORDS
    ]


def retrieve_materials(documents, query, facts, top_k=5):
    """Return the actual downstream payload, including every source restriction.

    Current documents are manual pages or article sections (196 records). Keeping
    these units whole avoids cutting a warning off the end of a numbered list.
    """
    pool = [
        doc
        for doc in documents
        if not doc.get("is_archived") and document_matches(doc, facts)
    ]
    query_terms = Counter(terms(query + " " + (facts.get("exact_error") or "")))
    if not pool or not query_terms:
        return []
    bodies = [Counter(terms(doc["content"])) for doc in pool]
    titles = [Counter(terms(doc["title"])) for doc in pool]
    frequency = Counter(term for body in bodies for term in body)
    average = sum(sum(body.values()) for body in bodies) / len(bodies) or 1
    scored = []
    for doc, body, title in zip(pool, bodies, titles):
        length = sum(body.values())
        score = 0.0
        for term in query_terms:
            count = body[term]
            idf = math.log(
                1 + (len(pool) - frequency[term] + 0.5) / (frequency[term] + 0.5)
            )
            score += idf * (
                count * 2.2 / (count + 1.2 * (0.25 + 0.75 * length / average))
            )
            score += idf * min(title[term], 1) * 2
        error = (facts.get("exact_error") or "").strip().casefold()
        if error and error in doc["content"].casefold():
            score += 6
        if score > 0:
            scored.append((score, str(doc["id"]), doc))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "document_id": str(doc["id"]),
            "title": doc["title"],
            "url": doc["source_url"],
            "text": doc["content"],
            "checksum": doc["checksum"],
            "score": round(score, 5),
            "kind": "source_material",
            "executable": False,
        }
        for score, _, doc in scored[:top_k]
    ]
