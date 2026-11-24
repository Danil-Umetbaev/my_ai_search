import unittest

import httpx
from pydantic import ValidationError

from src.ai.ingestion.dreamkas import DreamkasKnowledgeSource
from src.schemas.admin import DocumentImport


ARTICLE = "https://help.dreamkas.ru/kb/viki-printy/article/"
HTML = """<h1>Проверка печати</h1><nav>Лишнее меню</nav>
<div class="articles__page-instructions"><p>Откройте руководство кассы.
Проверьте установку бумаги по схеме производителя и сравните результат печати.</p>
<ol><li>Первый шаг.</li><li>Второй шаг.</li></ol>
<img src="/paper.png" alt="Схема установки"><script>bad()</script></div>"""


class KnowledgeImportTests(unittest.IsolatedAsyncioTestCase):
    def test_url_policy(self):
        self.assertEqual(DocumentImport(url=ARTICLE + "?utm=test#part").url, ARTICLE)
        self.assertIn("/pages/123", DocumentImport(url="https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/123/name").url)
        for url in ("http://help.dreamkas.ru/kb/test", "https://127.0.0.1/kb/test", "https://help.dreamkas.ru.evil.test/kb/test", "https://u:p@help.dreamkas.ru/kb/test", "https://help.dreamkas.ru:8080/kb/test"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                DocumentImport(url=url)

    async def test_article_preserves_steps_and_image_references(self):
        source = DreamkasKnowledgeSource(httpx.MockTransport(lambda r: httpx.Response(200, text=HTML, headers={"content-type": "text/html"})))
        doc = await source.fetch(ARTICLE)
        self.assertEqual(doc.source_type, "html")
        self.assertIn("1. Первый шаг", doc.content)
        self.assertIn("2. Второй шаг", doc.content)
        self.assertNotIn("Лишнее меню", doc.content)
        self.assertNotIn("bad()", doc.content)
        self.assertEqual(doc.images[0].source_url, "https://help.dreamkas.ru/paper.png")

    async def test_redirect_cannot_reach_other_hosts(self):
        requests = []
        def handle(request):
            requests.append(str(request.url))
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        with self.assertRaises(ValueError):
            await DreamkasKnowledgeSource(httpx.MockTransport(handle)).fetch(ARTICLE)
        self.assertEqual(requests, [ARTICLE])

    def test_category_is_not_a_document(self):
        with self.assertRaises(ValueError):
            DreamkasKnowledgeSource().parse(b"<h1>Category</h1><a>Article</a>", ARTICLE)
