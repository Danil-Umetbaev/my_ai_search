from httpx import AsyncClient

from src.main import app
from src.api.dependencies import (
    get_rag_service,
    get_notification_provider
)

from tests.fakes.rag import (
    AnsweredFakeRAGService,
    NotFoundFakeRAGService
)

from tests.fakes.notifications import (
    FakeNotificationProvider,
    FailNotificationProvider
)


async def create_conversation(client: AsyncClient) -> str:
    response = await client.post("/api/v1/conversations")

    assert response.status_code == 200

    return response.json()["id"]


async def test_chat_answered(client: AsyncClient):
    notification_provider = FakeNotificationProvider()

    app.dependency_overrides[get_rag_service] = (
        lambda: AnsweredFakeRAGService()
    )

    app.dependency_overrides[get_notification_provider] = (
        lambda: notification_provider
    )

    conversation_id = await create_conversation(client)

    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "Тестовый вопрос"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "answered"
    assert data["answer"] == "Тестовый ответ из документации."
    assert data["message"] is None
    assert data["confidence"] == 0.95
    assert data["sources"] == []

    assert notification_provider.called is False

    history_response = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages"
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 2

    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Тестовый вопрос"

    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Тестовый ответ из документации."


async def test_chat_escalated(client: AsyncClient):
    notification_provider = FakeNotificationProvider()

    app.dependency_overrides[get_rag_service] = (
        lambda: NotFoundFakeRAGService()
    )

    app.dependency_overrides[get_notification_provider] = (
        lambda: notification_provider
    )

    conversation_id = await create_conversation(client)

    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "Как оформить отпуск сотруднику?"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "not_found"
    assert data["answer"] is None
    assert data["message"] == (
        "В документации не найден ответ. Обращение сохранено для специалиста. Уведомление отправлено."
    )
    assert data["sources"] == []
    assert data["confidence"] == 0.10

    assert notification_provider.called is True
    assert notification_provider.question == (
        "Как оформить отпуск сотруднику?"
    )

    history_response = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages"
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 2

    assert history[0]["role"] == "user"
    assert history[0]["content"] == (
        "Как оформить отпуск сотруднику?"
    )

    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == data["message"]


async def test_chat_escalated_when_notification_fails(
    client: AsyncClient
):
    notification_provider = FailNotificationProvider()

    app.dependency_overrides[get_rag_service] = (
        lambda: NotFoundFakeRAGService()
    )

    app.dependency_overrides[get_notification_provider] = (
        lambda: notification_provider
    )

    conversation_id = await create_conversation(client)

    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "Неизвестный вопрос"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "not_found"
    assert data["answer"] is None
    assert data["message"] == (
        "В документации не найден ответ. Обращение сохранено для специалиста. Уведомление доставить не удалось."
    )

    assert notification_provider.called is True

    history_response = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages"
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


async def test_rag_owner_protected_before_and_after_first_message(client):
    from tests.integration.test_support import account
    await account(client)
    app.dependency_overrides[get_rag_service] = lambda: AnsweredFakeRAGService()
    cid = await create_conversation(client)
    owner_cookies = dict(client.cookies)
    client.cookies.clear()
    path = f"/api/v1/conversations/{cid}/messages"
    assert (await client.get(path)).status_code == 404
    client.cookies.update(owner_cookies)
    body = {"conversation_id": cid, "message": "Тестовый вопрос"}
    assert (await client.post("/api/v1/chat/messages", json=body)).status_code == 200
    await account(client, "other@example.com")
    assert (await client.get(path)).status_code == 404
    assert (await client.post("/api/v1/chat/messages", json=body)).status_code == 404
    client.cookies.clear()
    assert (await client.get(path)).status_code == 404
    client.cookies.update(owner_cookies)
    assert len((await client.get(path)).json()) == 2


async def test_rag_concurrent_retries_and_conflicting_request(client):
    import asyncio
    from uuid import uuid4
    from unittest.mock import AsyncMock
    rag = AnsweredFakeRAGService()
    rag.answer = AsyncMock(wraps=rag.answer)
    app.dependency_overrides[get_rag_service] = lambda: rag
    cid = await create_conversation(client)
    body = {"conversation_id": cid, "message": "Тестовый вопрос", "request_id": str(uuid4())}
    replies = await asyncio.gather(*(
        client.post("/api/v1/chat/messages", json=body) for _ in range(3)
    ))
    assert all(r.status_code == 200 for r in replies)
    assert all(r.json() == replies[0].json() for r in replies)
    rag.answer.assert_awaited_once()
    replay = await client.post("/api/v1/chat/messages", json=body)
    assert replay.json() == replies[0].json()
    conflict = await client.post("/api/v1/chat/messages", json={**body, "message": "Другой вопрос"})
    assert conflict.status_code == 409
    assert len((await client.get(f"/api/v1/conversations/{cid}/messages")).json()) == 2


async def test_not_found_retry_creates_one_escalation(client):
    from uuid import uuid4
    from sqlalchemy import text
    from tests.conftest import test_session_maker
    provider = FakeNotificationProvider()
    app.dependency_overrides[get_rag_service] = lambda: NotFoundFakeRAGService()
    app.dependency_overrides[get_notification_provider] = lambda: provider
    cid = await create_conversation(client)
    body = {"conversation_id": cid, "message": "Тестовый вопрос", "request_id": str(uuid4())}
    first = await client.post("/api/v1/chat/messages", json=body)
    second = await client.post("/api/v1/chat/messages", json=body)
    assert first.status_code == 200
    assert first.json() == second.json()
    async with test_session_maker() as db:
        count = await db.scalar(text("SELECT count(*) FROM escalations WHERE conversation_id=:id"), {"id": cid})
    assert count == 1
