"""Store selected conditions independently from the user's original wording."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def configuration():
    path = Path(__file__).resolve().parents[2] / "data" / "atol_answer_flow.json"
    return json.loads(path.read_text(encoding="utf-8"))


def record(state, node_id, choice_index):
    binding = configuration()["facts"].get(node_id)
    if binding is None:
        return
    flow = state["_atol_tree"]
    answers = flow.setdefault("answers", [])
    index = next((i for i, item in enumerate(answers) if item["field"] == binding["field"]), len(answers))
    removed = answers[index:]
    value = binding["values"][choice_index]
    if removed:
        state.setdefault("fact_changes", []).append({
            "field": binding["field"], "previous": removed[0]["value"],
            "value": value, "invalidated": [item["field"] for item in removed[1:]],
        })
    answers[index:] = [{"node": node_id, "field": binding["field"], "value": value}]
    state["paper_facts"] = {item["field"]: item["value"] for item in answers}
