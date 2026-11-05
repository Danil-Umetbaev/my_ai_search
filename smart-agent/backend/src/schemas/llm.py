from pydantic import BaseModel, Field

class LLMAnswerSchema(BaseModel):
    answerable: bool
    answer: str | None
    source_titles: list[str] = Field(default_factory=list)


class RewriteQuerySchema(BaseModel):
    relevant: bool
    rewritten_query: str | None
