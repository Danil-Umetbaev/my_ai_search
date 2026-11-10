"""Deterministic navigation through the reviewed ATOL manual catalog."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from src.services import atol_problem_router


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
    return [
        {"id": f"atol:{flow['revision']}:{index}", "label": item["label"]}
        for index, item in enumerate(available_options(flow))
    ]


def available_options(flow):
    nodes = catalog()["nodes"]
    if flow.get("proposal") is not None:
        return atol_problem_router.proposal_options(flow, nodes)
    return nodes[flow["node"]].get("choices", [])


def render(state):
    flow = state["_atol_tree"]
    if flow.get("proposal") is not None:
        return atol_problem_router.proposal_text(flow)
    node = catalog()["nodes"][flow["node"]]
    parts = [node["text"]]
    if atol_problem_router.can_suggest(flow["node"]):
        parts.append("Можно выбрать кнопку или описать проблему своими словами.")
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
    options = available_options(flow)
    proposal = flow.get("proposal")
    selected = next((c for c in options if c["label"].casefold() == normalized), None)
    if proposal is not None and not selected:
        if normalized in {"да", "верно", "правильно"} and len(proposal["targets"]) == 1:
            selected = options[0]
        elif normalized in {"нет", "назад"}:
            selected = options[-1]
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
            return state, "Заявка не отправлена. Можно подтвердить передачу или отменить обращение."
        else:
            state["additional_context"] = message
            return state, "Передать обращение специалисту? Выберите отправку с дополнением или без него либо отмените обращение."
    if not target:
        if atol_problem_router.can_suggest(flow["node"]):
            flow["proposal"] = {"targets": atol_problem_router.suggest(message), "description": message}
            flow["revision"] += 1
            state.setdefault("observations", []).append({"question": "Описание проблемы", "answer": message})
            return state, render(state)
        return state, "Выберите подходящую кнопку ниже. Если варианта нет, можно обратиться к специалисту."
    state.setdefault("observations", []).append({"question": current["text"], "answer": message})
    if flow["node"] == "model" and target in {"menu", "categories"}:
        state["environment"] = "АТОЛ FPrint-22ПТК"
    if flow["node"] == "menu" or (selected and selected.get("action") == "select_problem"):
        state["problem"] = message
    if proposal is not None:
        if selected and selected.get("action") == "select_problem":
            state["problem"] = proposal["description"]
        flow.pop("proposal", None)
    if current["kind"] == "instruction" and selected and selected.get("action") == "outcome":
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
