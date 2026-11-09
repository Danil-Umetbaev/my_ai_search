"""Known procedures and model-scoped source retrieval use separate paths."""

from src.services.base import BaseService
from src.services.receipt_procedures import (
    catalog,
    clarification,
    infer_intent,
    render_procedure,
    select_procedure,
)
from src.services.support_retrieval import retrieve_materials
from src.services.receipt_reference import select_reference, explain_reference


class SupportKnowledgeService(BaseService):
    async def lookup(self, query, flow, role):
        facts = {**flow.get("facts", {}), "allowed_operator": role in {"admin", "it"}}
        active = next(
            (
                p
                for p in catalog()["procedures"]
                if p["id"] == flow.get("active_procedure")
            ),
            None,
        )
        if active:
            documents = await self.db.documents.get_support_documents()
            verified = render_procedure(active, documents)
            if verified["status"] == "blocked":
                return verified
        reference = select_reference(query, facts, preferred=True)
        if reference:
            documents = await self.db.documents.get_support_documents()
            explanation = explain_reference(reference, documents, facts)
            if explanation:
                return explanation
        intent = infer_intent(query, facts)
        for field in (
            catalog()["routing"].get("intent_requirements", {}).get(intent, [])
        ):
            if field not in facts:
                return clarification(field, catalog()["procedures"])
            if facts[field] is None:
                return {
                    "status": "blocked",
                    "reason": "Не удалось уточнить необходимые наблюдения. Нужна помощь специалиста.",
                }
        selected = select_procedure(facts, intent)
        if selected["status"] == "clarify":
            return selected
        if selected["status"] == "blocked":
            procedure = selected.get("procedure", {})
            missing = procedure.get("missing_materials", [])
            review = procedure.get("specialist_review", {}).get("questions", [])
            return {
                "status": "blocked",
                "missing_elements": missing,
                "reason": selected.get("reason")
                or "Процедура требует проверки специалистом."
                + (
                    " Не хватает: " + "; ".join(missing)
                    if missing
                    else " Специалисту нужно: " + "; ".join(review) if review else ""
                ),
            }
        documents = await self.db.documents.get_support_documents()
        if selected["status"] == "selected":
            procedure = selected["procedure"]
            if procedure["id"] in flow.get("completed_procedures", []):
                return {
                    "status": "blocked",
                    "reason": "Эта проверка уже выполнена. Следующий шаг нужно согласовать со специалистом.",
                }
            return render_procedure(procedure, documents)
        materials = retrieve_materials(documents, query, facts)
        reference = select_reference(query, facts)
        if reference:
            explanation = explain_reference(reference, documents, facts)
            if explanation:
                return {**explanation, "materials": materials}
        return {
            "status": "answered" if materials else "not_found",
            "kind": "information",
            "answer": "Найдены связанные материалы по вашей модели, но их недостаточно для подтверждённого ответа по указанным условиям.",
            "sources": [
                {"title": item["title"], "url": item["url"]} for item in materials
            ],
            "materials": materials,
            "reason": "Материалы передадим специалисту вместе с наблюдениями; автоматически выполнять непроверенные действия не будем.",
        }
