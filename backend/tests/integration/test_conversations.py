from httpx import AsyncClient

async def test_create_conversation(client: AsyncClient):
    response = await client.post('/api/v1/conversations')

    assert response.status_code == 200

    data = response.json()

    assert 'id' in data
    assert 'created_at' in data

async def test_empty_conversation_history(client: AsyncClient):
    response = await client.post('/api/v1/conversations')

    assert response.status_code == 200

    data = response.json()

    response_history = await client.get(f"/api/v1/conversations/{data['id']}/messages")

    assert response_history.status_code == 200
    assert response_history.json() == []