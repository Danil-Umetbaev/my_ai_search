from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):

    @abstractmethod
    def embed_query(self, message: str) -> list[float]:
        ...


    @abstractmethod
    def embed_document(self, messages: list[str]) -> list[list[float]]:
        ...