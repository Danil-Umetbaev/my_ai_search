"""Continue an unmatched ATOL description using model-scoped reviewed materials."""

from copy import deepcopy

from src.services import atol_support_tree as tree
from src.services.receipt_choices import choices_for, choice_fact
from src.services.receipt_diagnosis import respond_receipt
from src.services.receipt_facts import ALIASES, check_result, extract_candidates


BACK = "Вернуться к разделам"


def options(state):
    return choices_for({"_receipt": state.get("_receipt", {})})


def match_option(state, message):
    receipt = state["_receipt"]
    choices = options(state)
    exact = next((item for item in choices if item["label"].casefold() == message.casefold()), None)
    if exact:
        return exact
    field = receipt.get("pending")
    if field == "result":
        outcome = check_result(message)
        if "problem_resolved" in outcome:
            value = outcome["problem_resolved"]
            index = {True: 0, False: 1, None: 2}[value]
            return choices[index]
    field = ALIASES.get(field, field)
    values = {value for _, value in extract_candidates(message, field).get(field, [])}
    if len(values) == 1:
        return next((item for item, option in zip(choices, receipt.get("question_options", []))
                     if option["value"] in values), None)
    return None


def start(state, description):
    state = deepcopy(state)
    facts = {**state.get("receipt_facts", {}), "model": "АТОЛ FPrint-22ПТК"}
    bindings = {
        "Наличие рулона": ("paper_present", {"Рулон установлен": True, "Бумага закончилась": False}),
        "Ширина ленты": ("paper_width_mm", {"80 мм": 80, "58 мм": 58}),
        "Положение кассы": ("layout", {"Вертикально": "vertical", "Горизонтально": "horizontal"}),
    }
    for field, value in state.get("paper_facts", {}).items():
        if field in bindings:
            key, values = bindings[field]
            facts[key] = values.get(value)
    receipt = state.setdefault("_receipt", {})
    receipt.update(facts=facts, problem_facts_loaded=True)
    state["problem"] = description
    flow = state["_atol_tree"]
    flow.pop("proposal", None)
    flow["manual"] = True
    return state


async def search(state, message, lookup, *, button=False):
    state = deepcopy(state)
    flow = state["_atol_tree"]
    flow["revision"] += 1
    normalized = message.strip().casefold().rstrip(".!?")
    offer = flow.pop("manual_offer", None)
    if normalized == BACK.casefold():
        flow.pop("manual")
        flow.pop("manual_reply", None)
        state["_receipt"].pop("pending", None)
        state["_receipt"].pop("question_options", None)
        state["_receipt"].pop("active_procedure", None)
        flow["node"] = "categories"
        return state, tree.render(state)
    original = message
    if offer:
        if normalized in {"нет", "нет, выбрать снова", "назад"}:
            return state, tree.render(state)
        if normalized in {"да", "да, верно", "верно", "правильно"}:
            original, message, button = offer["description"], offer["label"], True
    selected = match_option(state, message) if options(state) else None
    if not button and options(state):
        if selected:
            flow["manual_offer"] = {"description": message, "label": selected["label"]}
        return state, tree.render(state)
    selected_fact = choice_fact({"_receipt": state["_receipt"]}, selected["id"]) if selected else None
    old_sources = state.get("sources", [])
    updated, answer = await respond_receipt(state, message, lookup, selected_fact=selected_fact)
    if original != message and updated.get("observations"):
        updated["observations"][-1].update(answer=original, selected_answer=message)
    updated["sources"] = old_sources + [s for s in updated.get("sources", []) if s not in old_sources]
    if updated.get("_phase") in {"confirm", "resolved"}:
        flow = updated["_atol_tree"]
        flow.pop("manual", None)
        flow["node"] = "handoff" if updated["_phase"] == "confirm" else "resolved"
        flow.pop("manual_reply", None)
        if updated["_phase"] == "confirm" and not state["_receipt"].get("pending"):
            flow.update(node="categories", proposal={"targets": [], "description": message})
            updated["_phase"] = "diagnosing"
            answer = answer.partition("\n\nПередать обращение специалисту")[0]
            answer += "\n\nМожно уточнить описание, выбрать раздел или передать обращение специалисту."
            flow["proposal"]["search_reply"] = answer
    else:
        updated["_atol_tree"]["manual_reply"] = answer
    return updated, answer
