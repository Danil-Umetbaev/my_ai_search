
from httpx import AsyncClient


async def test_health(client: AsyncClient):

    response = await client.get('/api/v1/health')

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}