from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

from src.schemas.rag import RAGStatus

class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str

class SourceResponse(BaseModel):
    title: str
    url: str
    score: float


class ChatResponse(BaseModel):
    message_id: UUID | None = None
    status: RAGStatus
    answer: str | None
    sources: list[SourceResponse] = Field(default_factory=list)
    confidence: float | None

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


