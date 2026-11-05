from abc import ABC, abstractmethod

class RerankerProvider(ABC):

    @abstractmethod
    def rerank(
            query: str,
            documents: list[str]
    ) -> list[float]:
        pass

