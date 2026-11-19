from uuid import uuid4
from src.main import app
from src.api.dependencies import get_rag_service
from tests.fakes.rag import AnsweredFakeRAGService
from tests.integration.test_support import account


async def start(client):
    app.dependency_overrides[get_rag_service] = lambda: AnsweredFakeRAGService()
    await account(client)
    return (await client.post("/api/v1/conversations")).json()["id"]


async def post(client, cid, message, choice_id=None, request_id=None):
    r = await client.post("/api/v1/chat/messages", json={
        "conversation_id": cid, "message": message, "choice_id": choice_id,
        "request_id": request_id or str(uuid4()),
    })
    assert r.status_code == 200, r.text
    return r.json()


async def press(client, cid, reply, label):
    choice = next(c for c in reply["choices"] if c["label"] == label)
    return await post(client, cid, label, choice["id"])


async def test_main_chat_diagnosis_reload_ticket_and_ownership(client):
    cid = await start(client)
    faq = await post(client, cid, "Как заменить ленту?")
    assert faq["answer"] == "Тестовый ответ из документации."
    assert faq["choices"] == []
    reply = await post(client, cid, "Атол зажевало бумагу")
    assert reply["phase"] == "collect"
    reply = await press(client, cid, reply, "Да, верно")
    assert "Зажевало бумагу" in [c["label"] for c in reply["choices"]]
    history = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert history[-1]["response_meta"]["choices"] == reply["choices"]
    stale = reply["choices"][0]
    reply = await press(client, cid, reply, "Зажевало бумагу")
    rejected = await client.post("/api/v1/chat/messages", json={
        "conversation_id": cid, "message": stale["label"], "choice_id": stale["id"],
    })
    assert rejected.status_code == 409
    reply = await post(client, cid, "передать специалисту")
    choice = next(c for c in reply["choices"] if c["label"] == "Отправить специалисту")
    rid = str(uuid4())
    first = await post(client, cid, choice["label"], choice["id"], rid)
    replay = await post(client, cid, choice["label"], choice["id"], rid)
    assert first == replay
    assert first["phase"] == "ticket_created"
    tickets = (await client.get("/api/v1/support/tickets")).json()
    assert len(tickets) == 1
    detail = (await client.get("/api/v1/support/tickets/" + tickets[0]["id"])).json()
    assert detail["details"]["environment"] == "АТОЛ FPrint-22ПТК"
    assert detail["history"][0]["content"] == "Как заменить ленту?"
    await account(client, "second@example.org")
    assert (await client.get(f"/api/v1/conversations/{cid}/messages")).status_code == 404
    assert (await client.post("/api/v1/chat/messages", json={"conversation_id": cid, "message": "да"})).status_code == 404


async def test_pirit_typo_and_resolution(client):
    cid = await start(client)
    reply = await post(client, cid, "непечатает чек пирит")
    reply = await press(client, cid, reply, "Да, верно")
    reply = await press(client, cid, reply, "Да, верно")
    assert "Закончилась лента" in [c["label"] for c in reply["choices"]]
    for label in ("Закончилась лента", "Рулон закончился", "Да, помогло"):
        reply = await press(client, cid, reply, label)
    assert reply["phase"] == "resolved" and not reply["choices"]
    assert (await client.get("/api/v1/support/tickets")).json() == []
    faq = await post(client, cid, "Как заменить ленту?")
    assert faq["answer"] == "Тестовый ответ из документации."


async def test_diagnosis_is_available_while_search_loads(client):
    await account(client)
    app.state.models = {"status": "loading"}
    cid = (await client.post("/api/v1/conversations")).json()["id"]
    reply = await post(client, cid, "непечатает чек пирит")
    assert reply["choices"]
    reply = await press(client, cid, reply, "Да, верно")
    assert reply["choices"]

