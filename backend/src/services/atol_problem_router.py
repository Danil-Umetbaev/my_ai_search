"""Suggest reviewed tree entries without selecting a repair or changing facts."""

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def routing_catalog():
    path = Path(__file__).resolve().parents[2] / "data" / "atol_problem_routes.json"
    return json.loads(path.read_text(encoding="utf-8"))


def suggest(message):
    data = routing_catalog()
    text = re.sub(r"\s+", " ", message.casefold().replace("ё", "е")).strip()
    for typo, word in data["corrections"].items():
        text = re.sub(rf"\b{re.escape(typo)}\b", word, text)
    if any(re.search(pattern, text) for pattern in data["unsupported"]):
        return []
    for rules in (data["problems"], data["groups"]):
        targets = []
        for rule in rules:
            if any(re.search(pattern, text) for pattern in rule.get("exclude", [])):
                continue
            if any(re.search(pattern, text) for pattern in rule["patterns"]):
                targets.append(rule["target"])
        if targets:
            return targets if len(targets) <= 3 else []
    return []


def can_suggest(node_id):
    return node_id in {"categories", "menu", "choose_help"} or node_id.startswith("group_")


def proposal_options(flow, nodes):
    proposal = flow["proposal"]
    labels = {
        choice["next"]: choice["label"]
        for node_id in ("menu", "categories")
        for choice in nodes[node_id]["choices"]
    }
    options = [
        {"label": labels[target], "next": target, "action": "select_problem"}
        for target in proposal["targets"]
    ]
    return options + [{"label": "Выбрать по кнопкам", "next": "categories"}]


def proposal_text(flow):
    targets = flow["proposal"]["targets"]
    if not targets:
        return "Не удалось уверенно подобрать вариант. Опишите, что происходит с кассой, или выберите проблему по кнопкам."
    if len(targets) > 1:
        return "В описании подходят несколько вариантов. Что сейчас происходит? Выберите подходящий или уточните описание."
    if targets[0].startswith("group_"):
        return "Похоже, проблема относится к этому разделу. Открыть его?"
    return "Правильно понял проблему? Подтвердите вариант ниже или опишите её иначе."
