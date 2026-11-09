"""Equipment boundaries shared by procedure selection and support retrieval."""

import re


def canonical_model(value):
    text = (value or "").casefold().replace("ё", "е")
    if re.search(r"(?:fprint|фпринт|атол)[ -]*22\s*птк\b", text):
        return "АТОЛ FPrint-22ПТК"
    if re.search(r"пирит\s*2\s*[фf]\b", text):
        return "Пирит 2Ф"
    match = re.search(
        r"(?:вики\s*принт|viki\s*print)(?:\s*(57|80)(?:\s*(плюс|plus))?(?:\s*(ф))?)?",
        text,
    )
    if match:
        return (
            "Вики Принт"
            + (" " + match[1] if match[1] else "")
            + (" Плюс" if match[2] else "")
            + (" Ф" if match[3] else "")
        )
    return None


def model_matches(actual, required):
    actual = canonical_model(actual)
    required = canonical_model(required)
    if not actual or not required:
        return False
    return actual == required or (
        required == "Вики Принт" and actual.startswith("Вики Принт ")
    )


def document_matches(document, facts):
    actual = canonical_model(facts.get("model"))
    if not actual:
        return False
    models = document.get("equipment_models") or []
    title_model = canonical_model(document["title"])
    explicit = re.search(
        r"подходит только для ([^.\n]+)", document.get("content", "")[:500], re.I
    )
    if explicit:
        title_model = canonical_model(explicit[1]) or title_model
        year = re.search(r"начиная с (20\d\d) года", explicit[1])
        if year and (
            facts.get("production_year") is None
            or facts["production_year"] < int(year[1])
        ):
            return False
    if title_model:
        models = [title_model]
    if not models and "/kb/viki-printy/" in document.get("source_url", ""):
        models = ["Вики Принт"]
    if not any(model_matches(actual, model) for model in models):
        return False
    version = document.get("software_version")
    if version and facts.get("platform") and version != facts["platform"]:
        return False
    return True
