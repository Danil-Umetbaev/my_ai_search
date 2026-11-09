"""Select and validate catalog data. No database calls or generated instructions."""

import json
import re
from functools import lru_cache
from pathlib import Path

from src.services.equipment_scope import document_matches, model_matches
from src.services.receipt_facts import normalize

DATA = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def catalog():
    return json.loads((DATA / "receipt_procedures.json").read_text(encoding="utf-8"))


def infer_intent(query, facts):
    rules = catalog()["routing"]
    text = normalize(query)
    symptom_intent = rules["symptom_intents"].get(facts.get("symptom"))
    for intent, pattern in rules["intent_patterns"]:
        if (
            intent == "width_setting"
            and facts.get("paper_present") is False
            and facts.get("driver_width_mm") is not None
            and facts["driver_width_mm"] == facts.get("paper_width_mm")
        ):
            continue
        if (
            intent in {"paper_jam", "paper_skew", "qr_missing"}
            and symptom_intent
            and intent != symptom_intent
        ):
            continue
        if re.search(pattern, text):
            return intent
    if facts.get("paper_present") is False:
        return "paper_installation"
    return symptom_intent or "documentation"


def condition_matches(facts, condition):
    key = condition["fact"]
    actual = facts.get(key)
    if actual is None:
        return False
    if key == "model":
        return model_matches(actual, condition["equals"])
    expected = condition.get("one_of", [condition.get("equals")])
    return any(type(actual) is type(value) and actual == value for value in expected)


def clarification(field, procedures):
    question = next(
        q["question"]
        for p in procedures
        for q in p["clarifications"]
        if q["fact"] == field
    )
    values = catalog()["routing"]["choices"].get(field)
    if values is None:
        constraints = [
            r
            for p in procedures
            for r in p["applicability"]["all_of"]
            if r["fact"] == field
        ]
        values = (
            [[True, "Да"], [False, "Нет"]]
            if any(type(r.get("equals")) is bool for r in constraints)
            else []
        )
    choices = [{"value": value, "label": label} for value, label in values]
    choices.append({"value": None, "label": "Не знаю / не могу проверить"})
    return {
        "status": "clarify",
        "field": field,
        "question": question,
        "choices": choices,
    }


def select_procedure(facts, intent):
    candidates = []
    for procedure in catalog()["procedures"]:
        route = procedure["routing"]
        if intent not in route["intents"]:
            continue
        if any(facts.get(key) is not None for key in route["exclude_when_known"]):
            continue
        conditions = procedure["applicability"]["all_of"]
        if any(
            facts.get(r["fact"]) is not None and not condition_matches(facts, r)
            for r in conditions
        ):
            continue
        missing = [r["fact"] for r in conditions if facts.get(r["fact"]) is None]
        candidates.append((procedure, missing))
    complete = [(p, missing) for p, missing in candidates if not missing]
    if complete:
        procedure = sorted(
            complete,
            key=lambda item: (
                item[0]["status"] != "ready",
                -len(item[0]["applicability"]["all_of"]),
                item[0]["id"],
            ),
        )[0][0]
        return {
            "status": "selected" if procedure["status"] == "ready" else "blocked",
            "procedure": procedure,
        }
    ready = [(p, m) for p, m in candidates if p["status"] == "ready"]
    if not ready:
        if candidates:
            return {"status": "blocked", "procedure": candidates[0][0]}
        return {"status": "search"}
    ready.sort(key=lambda item: (len(item[1]), item[0]["id"]))
    procedure, missing = ready[0]
    for field in missing:
        if field in facts or field == "allowed_operator":
            return {
                "status": "blocked",
                "reason": "Не удалось подтвердить обязательное условие: "
                + next(
                    q["question"]
                    for q in procedure["clarifications"]
                    if q["fact"] == field
                ),
            }
    common = set.intersection(*(set(missing) for _, missing in ready))
    field = next((key for key in missing if key in common), missing[0])
    return clarification(field, [p for p, _ in ready])


def render_procedure(procedure, documents, assets_root=DATA):
    if procedure["status"] != "ready":
        return {
            "status": "blocked",
            "reason": "Процедура ещё не допущена к выполнению.",
        }
    sources = catalog()["sources"]
    model = next(
        rule["equals"]
        for rule in procedure["applicability"]["all_of"]
        if rule["fact"] == "model"
    )
    current = {str(doc["id"]): doc for doc in documents if not doc.get("is_archived")}
    links = []
    for ref in procedure["source_refs"]:
        source = sources[ref]
        doc = current.get(source["document_id"])
        if (
            not doc
            or doc["checksum"] != source["checksum"]
            or not document_matches(doc, {"model": model})
        ):
            return {
                "status": "blocked",
                "reason": "Источник инструкции изменился или недоступен. Нужна повторная проверка специалистом.",
            }
        links.append({"title": source["title"], "url": source["url"]})
    for ref in procedure["required_materials"]:
        material = catalog()["materials"][ref]
        path = (assets_root / material["local_file"]).resolve()
        if (
            not path.is_relative_to((assets_root / "knowledge_assets").resolve())
            or not path.is_file()
        ):
            return {
                "status": "blocked",
                "reason": "Обязательная схема или фотография инструкции недоступна.",
            }
        for page in material["pages"]:
            links.append(
                {
                    "title": material["description"],
                    "url": f"/api/v1/knowledge-assets/{path.name}#page={page}",
                }
            )
    steps = "\n\n".join(
        f"{step['order']}. {step['action']}" for step in procedure["steps"]
    )
    restrictions = "\n".join(
        procedure["documentation_restrictions"] + procedure["product_limits"]
    )
    answer = (
        steps
        + ("\n\nОграничения:\n" + restrictions if restrictions else "")
        + "\n\nОжидаемый результат: "
        + procedure["expected_result"]
    )
    return {
        "status": "answered",
        "kind": (
            "instruction" if procedure["kind"] == "instruction" else "diagnostic_check"
        ),
        "answer": answer,
        "sources": links,
        "procedure_id": procedure["id"],
        "result_question": procedure["result_question"],
        "result_action": procedure["on_success"],
    }
