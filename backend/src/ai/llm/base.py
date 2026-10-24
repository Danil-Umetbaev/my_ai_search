import re
from abc import ABC, abstractmethod
from src.schemas.llm import LLMAnswerSchema
class LLMProvider(ABC):

    @abstractmethod
    def generate(self, question: str, search_query: str, context: str) -> LLMAnswerSchema:
        pass

    @abstractmethod
    def rewrite_query(self, question: str) -> str:
        pass


def is_arithmetic_question(question: str) -> bool:
    number = r"(?:\d+(?:[.,]\d+)?|(?:ноль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять))"
    operator = r"(?:умножить на|разделить на|плюс|минус|на|[+*/×÷-])"
    return re.fullmatch(
        rf"(?:(?:сколько (?:будет|получится)|посчитай|вычисли)\s+)?{number}\s*{operator}\s*{number}[?!.]*",
        question.strip().lower(),
    ) is not None
