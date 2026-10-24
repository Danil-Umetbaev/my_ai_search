from pydantic import BaseModel

class LLMAnswerSchema(BaseModel):
    answerable: bool
    answer: str | None
    clarification: bool = False


class RewriteQuerySchema(BaseModel):
    relevant: bool
    rewritten_query: str | None
