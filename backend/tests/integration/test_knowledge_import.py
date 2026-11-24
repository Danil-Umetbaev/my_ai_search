import httpx
from sqlalchemy import text

from src.main import app
from src.api.dependencies import get_admin_service, DBDep
from src.ai.ingestion.dreamkas import DreamkasKnowledgeSource
from src.services.admin import AdminService
from src.services.document_indexer import DocumentIndexerService
from tests.integration.test_support import account
from tests.conftest import test_session_maker
from tests.test_knowledge_import_unit import ARTICLE, HTML


class Chunker:
    def split(self, value):
        return [value]


class Embedding:
    def embed_document(self, values):
        return [[0.1] * 1024 for _ in values]


async def test_import_refresh_and_duplicate(client):
    await account(client, role="admin")
    content = [HTML]
    source = DreamkasKnowledgeSource(httpx.MockTransport(
        lambda request: httpx.Response(200, text=content[0], headers={"content-type": "text/html"})
    ))
    def service(db: DBDep):
        return AdminService(db, source=source, indexer=DocumentIndexerService(db, Chunker(), Embedding()))
    app.dependency_overrides[get_admin_service] = service
    document_id = None
    try:
        response = await client.post("/api/v1/admin/documents/import", json={"url": ARTICLE})
        assert response.status_code == 201, response.text
        document_id = response.json()["id"]
        assert len(response.json()["images"]) == 1
        duplicate = await client.post("/api/v1/admin/documents/import", json={"url": ARTICLE})
        assert duplicate.status_code == 409
        content[0] = HTML.replace("Первый шаг", "Новый первый шаг")
        refreshed = await client.post(f"/api/v1/admin/documents/{document_id}/refresh")
        assert refreshed.status_code == 200, refreshed.text
        assert "Новый первый шаг" in refreshed.json()["content"]
        async with test_session_maker() as db:
            chunks = (await db.execute(text("SELECT content FROM document_chunks WHERE document_id=:id AND is_active"), {"id": document_id})).scalars().all()
        assert len(chunks) == 1 and "Новый первый шаг" in chunks[0]
    finally:
        if document_id:
            async with test_session_maker() as db:
                await db.execute(text("DELETE FROM document_chunks WHERE document_id=:id"), {"id": document_id})
                await db.execute(text("DELETE FROM documents WHERE id=:id"), {"id": document_id})
                await db.commit()
