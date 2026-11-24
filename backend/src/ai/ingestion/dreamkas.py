import hashlib
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Doctype, ProcessingInstruction

from src.ai.ingestion.base import KnowledgeSource
from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
from src.ai.ingestion.text_cleanup import clean_article
from src.schemas.admin import DocumentImport
from src.schemas.documents import DocumentAddSchema, DocumentImage


class DreamkasKnowledgeSource(KnowledgeSource):
    def __init__(self, transport=None):
        self.transport = transport

    async def fetch(self, url: str) -> DocumentAddSchema:
        url = DocumentImport(url=url).url
        async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
            for _ in range(5):
                if urlsplit(url).hostname != "help.dreamkas.ru":
                    raise ValueError("Redirect outside Dreamkas")
                async with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = DocumentImport(url=urljoin(url, response.headers["location"])).url
                        continue
                    response.raise_for_status()
                    if "text/html" not in response.headers.get("content-type", ""):
                        raise ValueError("Expected an HTML article")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 5_000_000:
                            raise ValueError("Article is too large")
                    return self.parse(bytes(body), url)
        raise ValueError("Too many redirects")

    def parse(self, html: bytes, url: str) -> DocumentAddSchema:
        soup = BeautifulSoup(html, "html.parser")
        article = soup.select_one(".articles__page-instructions")
        heading = soup.find("h1")
        if article is None or heading is None:
            raise ValueError("Use an article URL, not a category page")
        title = heading.get_text(" ", strip=True)
        images = []
        for position, img in enumerate(article.find_all("img")):
            source = urljoin(url, img.get("data-src") or img.get("src") or "")
            parsed = urlsplit(source)
            caption = img.get("alt") or img.get("title") or title
            if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
                images.append(DocumentImage(source_url=source, caption=caption, position=position))
            img.replace_with(soup.new_string(f"\n[Иллюстрация: {caption}]\n"))
        for node in article.select("script, style, iframe"):
            node.decompose()
        for node in list(article.descendants):
            if isinstance(node, (Doctype, ProcessingInstruction)):
                node.extract()
        content = clean_article(ConfluenceKnowledgeSource()._render(article))
        if len(content) < 80:
            raise ValueError("Article text is too short")
        return DocumentAddSchema(
            source_type="html", source_url=url, title=title, content=content,
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            manufacturer="Дримкас", images=images,
        )
