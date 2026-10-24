from abc import ABC, abstractmethod
from src.schemas.llm import LLMAnswerSchema
class LLMProvider(ABC):

    @abstractmethod
    def generate(self, question: str, search_query: str, context: str) -> LLMAnswerSchema:
        pass

    @abstractmethod
    def rewrite_query(self, question: str) -> str:
        pass
