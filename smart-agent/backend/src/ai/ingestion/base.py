from abc import ABC, abstractmethod

from src.schemas.documents import DocumentAddSchema

class KnowledgeSource(ABC):

    @abstractmethod
    async def fetch(self, url: str) -> DocumentAddSchema:
        pass

