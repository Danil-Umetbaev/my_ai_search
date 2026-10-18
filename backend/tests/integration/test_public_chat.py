from src.main import app
from src.api.dependencies import get_rag_service, get_notification_provider
from tests.fakes.rag import NotFoundFakeRAGService


async def test_unknown_question_without_notifications(client):
    app.dependency_overrides[get_rag_service] = lambda: NotFoundFakeRAGService()
    app.dependency_overrides[get_notification_provider] = lambda: None
    conversation = await client.post("/api/v1/conversations")
    response = await client.post("/api/v1/chat/messages", json={
        "conversation_id": conversation.json()["id"], "message": "Неизвестный вопрос",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"
    assert "передан" not in response.json()["message"]
    history = await client.get(f'/api/v1/conversations/{conversation.json()["id"]}/messages')
    assert len(history.json()) == 2
