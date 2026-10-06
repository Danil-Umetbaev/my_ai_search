from abc import ABC, abstractmethod

class LLMProvider(ABC):

    @abstractmethod
    def generate(self, question: str, context: str) -> str:
        pass

    @abstractmethod
    def rewrite_query(self, question: str) -> str:
        pass
    