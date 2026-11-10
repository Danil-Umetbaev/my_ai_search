"""Require explicit evidence for facts that the model must not guess."""

import re
from copy import deepcopy

from src.services.atol_answer_state import configuration


def policy(node_id):
    data = configuration()
    group = data["validation_groups"].get(node_id, node_id)
    return resolve_policy(data["validation"], group)


def resolve_policy(policies, name, visited=()):
    if name in visited:
        raise ValueError("Cyclic answer validation policy")
    own = policies.get(name, {})
    parent = own.get("extends")
    if parent and parent not in policies:
        raise ValueError("Unknown parent answer validation policy")
    result = resolve_policy(policies, parent, (*visited, name)) if parent else {}
    for key, value in own.items():
        if key == "extends":
            continue
        if isinstance(value, dict):
            section = result.setdefault(key, {})
            for index, patterns in value.items():
                section[index] = section.get(index, []) + patterns
        elif isinstance(value, list):
            result[key] = result.get(key, []) + value
        else:
            result[key] = deepcopy(value)
    return result


def matches(patterns, message):
    text = message.casefold().replace("ё", "е")
    return any(re.search(pattern, text) for pattern in patterns)


def blocked(node_id, message):
    return matches(policy(node_id).get("reject", []), message)


def explicit_choice(node_id, message):
    if blocked(node_id, message):
        return None
    found = [int(index) for index, patterns in policy(node_id).get("explicit", {}).items() if matches(patterns, message)]
    return found[0] if len(found) == 1 else None


def supported(node_id, index, message):
    rules = policy(node_id)
    if blocked(node_id, message):
        return False
    if matches(rules.get("negated", {}).get(str(index), []), message):
        return False
    evidence = rules.get("evidence", {}).get(str(index))
    return evidence is None or matches(evidence, message)
