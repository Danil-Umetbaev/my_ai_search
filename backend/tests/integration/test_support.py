import asyncio
from uuid import uuid4

from sqlalchemy import text

from src.main import app
from tests.conftest import test_session_maker as session_maker
from tests.test_support_agent_unit import FakeLLM


async def account(client, email="cashier@example.com", role="kassir"):
    password = "Example-password-123"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "role": "kassir"},
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    user = (await client.get("/api/v1/auth/me")).json()
    if role != "kassir":
        async with session_maker() as session:
            await session.execute(
                text("UPDATE users SET role=CAST(:role AS userrole) WHERE id=:id"),
                {"id": user["id"], "role": role},
            )
            await session.commit()
    return user


async def conversation(client):
    response = await client.post("/api/v1/support/sessions")
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def send(client, session_id, message, request_id=None):
    return await client.post(
        f"/api/v1/support/sessions/{session_id}/messages",
        json={"message": message, "request_id": request_id or str(uuid4())},
    )


async def create_ticket(client):
    session_id = await conversation(client)
    assert (await send(client, session_id, "Ошибка приложения")).status_code == 200
    response = await send(client, session_id, "передать специалисту")
    assert response.json()["phase"] == "confirm"
    response = await send(client, session_id, "да")
    assert response.status_code == 200, response.text
    return session_id, response.json()["ticket_id"]


async def test_support_requires_authentication_and_trusted_origin(client):
    assert (await client.post("/api/v1/support/sessions")).status_code == 401
    await account(client)
    assert (
        await client.post(
            "/api/v1/support/sessions", headers={"Origin": "http://untrusted.example"}
        )
    ).status_code == 403
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "password": "Example-password-123",
            "role": "admin",
        },
    )
    assert response.status_code == 403


async def test_owner_isolation_and_staff_queue(client):
    await account(client)
    session_id, ticket_id = await create_ticket(client)
    mine = await client.get("/api/v1/support/tickets")
    assert len(mine.json()) == 1
    assert (await client.get("/api/v1/support/tickets?queue=true")).status_code == 403
    await account(client, "other@example.com")
    assert (
        await client.get(f"/api/v1/support/sessions/{session_id}")
    ).status_code == 404
    assert (await send(client, session_id, "да")).status_code == 404
    assert (await client.get(f"/api/v1/support/tickets/{ticket_id}")).status_code == 404
    assert (await client.get("/api/v1/support/tickets")).json() == []
    await account(client, "support@example.com", "it")
    assert len((await client.get("/api/v1/support/tickets?queue=true")).json()) == 1
    assert (await client.get(f"/api/v1/support/tickets/{ticket_id}")).status_code == 200


async def test_replay_and_request_id_conflict(client):
    await account(client)
    session_id = await conversation(client)
    identifier = str(uuid4())
    first = await send(client, session_id, "Ошибка приложения", identifier)
    second = await send(client, session_id, "Ошибка приложения", identifier)
    assert first.json() == second.json()
    assert (
        await send(client, session_id, "Другая проблема", identifier)
    ).status_code == 409
    history = (await client.get(f"/api/v1/support/sessions/{session_id}")).json()[
        "history"
    ]
    assert len(history) == 2


async def test_confirmation_does_not_create_duplicate_ticket(client):
    await account(client)
    session_id, ticket_id = await create_ticket(client)
    assert (await send(client, session_id, "да")).json()["ticket_id"] == ticket_id
    detail = (await client.get(f"/api/v1/support/tickets/{ticket_id}")).json()
    assert detail["details"]["transcript"][0]["content"] == "Ошибка приложения"
    assert len(detail["events"]) == 1


async def test_status_resolution_version_and_audit(client):
    await account(client)
    _, ticket_id = await create_ticket(client)
    forbidden = await client.patch(
        f"/api/v1/support/tickets/{ticket_id}",
        json={"status": "in_progress", "version": 0},
    )
    assert forbidden.status_code == 403
    staff = await account(client, "support@example.com", "it")
    response = await client.patch(
        f"/api/v1/support/tickets/{ticket_id}",
        json={
            "status": "in_progress",
            "version": 0,
            "comment": "Проверяем подключение",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["assigned_to"] == staff["id"]
    assert response.json()["version"] == 1
    assert (
        await client.patch(
            f"/api/v1/support/tickets/{ticket_id}",
            json={"status": "resolved", "version": 0, "resolution": "Готово"},
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/api/v1/support/tickets/{ticket_id}",
            json={"status": "resolved", "version": 1, "resolution": "   "},
        )
    ).status_code == 422
    response = await client.patch(
        f"/api/v1/support/tickets/{ticket_id}",
        json={
            "status": "resolved",
            "version": 1,
            "resolution": "Восстановлено соединение",
        },
    )
    assert response.status_code == 200
    await client.post(
        "/api/v1/auth/login",
        json={"email": "cashier@example.com", "password": "Example-password-123"},
    )
    detail = (await client.get(f"/api/v1/support/tickets/{ticket_id}")).json()
    assert detail["resolution"] == "Восстановлено соединение"
    assert len(detail["events"]) == 3
    assert detail["events"][1]["payload"]["comment"] == "Проверяем подключение"


async def test_cancel_and_resolution_are_terminal(client):
    await account(client)
    session_id = await conversation(client)
    assert (await send(client, session_id, "отмена")).json()["phase"] == "cancelled"
    assert (await send(client, session_id, "да")).json()["ticket_id"] is None
    session_id = await conversation(client)
    assert (await send(client, session_id, "проблема решена")).json()[
        "phase"
    ] == "resolved"
    assert (await send(client, session_id, "да")).json()["ticket_id"] is None
    assert (await client.get("/api/v1/support/tickets")).json() == []


async def test_validation_pagination_and_empty_knowledge(client):
    await account(client)
    session_id = await conversation(client)
    assert (await send(client, session_id, "   ")).status_code == 422
    assert (await send(client, session_id, "a" * 4001)).status_code == 422
    assert (await client.get("/api/v1/support/tickets?limit=1000")).status_code == 422
    assert (
        await client.get("/api/v1/support/tickets?status=invalid")
    ).status_code == 422
    result = await client.get("/api/v1/support/status")
    assert result.status_code == 200
    assert result.json()["knowledge_ready"] is False


async def test_ai_plan_goes_through_real_api(client, monkeypatch):
    await account(client)
    app.state.models = {
        "status": "ready",
        "llm": FakeLLM(
            {
                "action": "ask",
                "question": "На соседнем рабочем месте такая же ошибка?",
                "facts": {"problem": "Нет связи"},
            }
        ),
        "embedding": object(),
    }

    async def search(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "src.services.support_dialogue.VectorSearchService.search", search
    )
    session_id = await conversation(client)
    result = (await send(client, session_id, "Нет связи")).json()
    assert result["engine"] == "llm"
    assert "соседнем" in result["answer"]
    row = (await client.get(f"/api/v1/support/sessions/{session_id}")).json()
    assert row["state"]["problem"] == "Нет связи"


async def test_concurrent_messages_do_not_overwrite_history(client, monkeypatch):
    await account(client)
    session_id = await conversation(client)
    ready = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def delayed(state, history, message, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            ready.set()
        await release.wait()
        return {"problem": message, "_phase": "collect"}, "Уточните устройство"

    monkeypatch.setattr("src.services.support_dialogue.respond", delayed)
    tasks = [
        asyncio.create_task(send(client, session_id, message))
        for message in ["Ошибка А", "Ошибка Б"]
    ]
    try:
        await asyncio.wait_for(ready.wait(), 5)
    finally:
        release.set()
    responses = await asyncio.gather(*tasks)
    assert sorted(response.status_code for response in responses) == [200, 409]
    row = (await client.get(f"/api/v1/support/sessions/{session_id}")).json()
    assert len(row["history"]) == 2
    assert row["version"] == 1
