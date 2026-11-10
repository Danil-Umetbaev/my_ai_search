"""Deterministic navigation through the reviewed ATOL manual catalog."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog():
    path = Path(__file__).resolve().parents[2] / "data" / "atol_support_tree.json"
    return json.loads(path.read_text(encoding="utf-8"))


def initial_state():
    return {"_atol_tree": {"node": catalog()["initial"], "revision": 0}, "_phase": "collect"}


def choices(state):
    flow = state["_atol_tree"]
    if state.get("_phase") in {"confirm", "resolved", "cancelled", "ticket_created"}:
        return []
    node = catalog()["nodes"][flow["node"]]
    return [
        {"id": f"atol:{flow['revision']}:{index}", "label": item["label"]}
        for index, item in enumerate(node.get("choices", []))
    ]


def render(state):
    node = catalog()["nodes"][state["_atol_tree"]["node"]]
    parts = [node["text"]]
    for image in node.get("images", []):
        parts.append(f"![{image['title']}]({image['url']})")
    for source in node.get("sources", []):
        parts.append(f"{source['title']}: {source['url']}")
    if node["kind"] == "instruction" and any(c["next"] == "resolved" for c in node["choices"]):
        parts.append("Помогло?")
    return "\n\n".join(parts)


def advance(state, message):
    state = deepcopy(state)
    flow = state["_atol_tree"]
    current = catalog()["nodes"][flow["node"]]
    normalized = message.strip().casefold().rstrip(".!?")
    if state.get("_phase") in {"resolved", "cancelled"}:
        return state, "Обращение завершено. Для другой проблемы начните новое обращение."
    if normalized in {"отмена", "отменить"}:
        state["_phase"] = "cancelled"
        return state, "Обращение отменено. Заявка не создана."
    selected = next((c for c in current.get("choices", []) if c["label"].casefold() == normalized), None)
    target = selected["next"] if selected else None
    if not target and current["kind"] == "instruction":
        outcomes = {"да": "Да, помогло", "помогло": "Да, помогло", "нет": "Не помогло", "не получилось": "Не помогло", "не могу": "Не могу выполнить"}
        selected = next((c for c in current.get("choices", []) if c["label"] == outcomes.get(normalized)), None)
        target = selected["next"] if selected else None
    if normalized in {"передать специалисту", "нужен специалист"}:
        target = "handoff"
    if current["kind"] == "input":
        state["additional_context"] = message
        target = "handoff"
    if state.get("_phase") == "confirm":
        if normalized in {"нет", "не отправлять"}:
            target = "menu"
        else:
            state["additional_context"] = message
            return state, "Передать обращение специалисту? Нажмите «Подтвердить заявку» или отмените обращение."
    if not target:
        return state, "Выберите подходящую кнопку ниже. Если варианта нет, можно обратиться к специалисту."
    state.setdefault("observations", []).append({"question": current["text"], "answer": message})
    if flow["node"] == "model" and target == "menu":
        state["environment"] = "АТОЛ FPrint-22ПТК"
    if flow["node"] == "menu":
        state["problem"] = message
    if current["kind"] == "instruction":
        state.setdefault("performed_checks", []).append({"instruction": current["text"], "result": message, "sources": current.get("sources", [])})
        state["check_result"] = message
    flow.update(node=target, revision=flow["revision"] + 1)
    node = catalog()["nodes"][target]
    state.update(_engine="rules", _phase={"handoff": "confirm", "resolved": "resolved"}.get(node["kind"], "diagnosing"))
    for source in node.get("sources", []):
        if source not in state.setdefault("sources", []):
            state["sources"].append(source)
    if target == "resolved":
        state["resolution"] = message
    return state, render(state)
