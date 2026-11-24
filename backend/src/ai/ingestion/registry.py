from urllib.parse import urlsplit

from src.ai.ingestion.base import KnowledgeSource
from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
from src.ai.ingestion.dreamkas import DreamkasKnowledgeSource
from src.schemas.admin import DocumentImport


class RegisteredKnowledgeSource(KnowledgeSource):
    def __init__(self, sources=None):
        self.sources = sources if sources is not None else {
            "crystals.atlassian.net": ConfluenceKnowledgeSource(),
            "help.dreamkas.ru": DreamkasKnowledgeSource(),
        }

    async def fetch(self, url):
        canonical = DocumentImport(url=url).url
        return await self.sources[urlsplit(canonical).hostname].fetch(canonical)
