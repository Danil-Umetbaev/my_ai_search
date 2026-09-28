from abc import ABC, abstractmethod

class Chunker(ABC):

    @abstractmethod
    def split(self, text: str) -> list[str]:
        ...