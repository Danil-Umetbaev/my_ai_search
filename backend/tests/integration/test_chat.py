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

    assert data["status"] == "escalated"
    assert data["answer"] is None
    assert data["message"] == (
        "Информация не найдена. Вопрос передан специалистам."
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
    assert history[1]["content"] == (
        "Информация не найдена. Вопрос передан специалистам."
    )


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

    assert data["status"] == "escalated"
    assert data["answer"] is None
    assert data["message"] == (
        "Информация не найдена. Вопрос передан специалистам."
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