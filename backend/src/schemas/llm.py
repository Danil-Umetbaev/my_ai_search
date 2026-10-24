from pydantic import BaseModel

class LLMAnswerSchema(BaseModel):
    answerable: bool
    answer: str | None


class RewriteQuerySchema(BaseModel):
    relevant: bool
    rewritten_query: str | None
