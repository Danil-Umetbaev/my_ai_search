from src.services import atol_semantic_router as router
from src.services.atol_support_tree import choices


async def confirm_answer(case, state, message, model):
    pending, prompt = await router.advance(state, message, [], model)
    offer = pending["_atol_tree"]["answer_offer"]
    case.assertIn(offer["label"], prompt)
    case.assertEqual(pending["_atol_tree"]["node"], state["_atol_tree"]["node"])
    for key in ("paper_facts", "diagnostic_facts", "performed_checks", "_phase"):
        case.assertEqual(pending.get(key), state.get(key))
    return await router.advance(pending, choices(pending)[0]["label"], [], model, button=True)
