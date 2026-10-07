from uuid import UUID

from pydantic import BaseModel, Field
from enum import StrEnum
class RAGStatus(StrEnum):
    ANSWERED = 'answered'
    NOT_FOUND = 'not_found'



class SourceSchema(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    url: str
    score: float

class RAGResultSchema(BaseModel):
    status: RAGStatus
    answer: str | None
    sources: list[SourceSchema] = Field(default_factory=list)
    confidence: float | None = None

