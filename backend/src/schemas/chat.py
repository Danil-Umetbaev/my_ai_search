from datetime import datetime
from pydantic import BaseModel, Field
from enum import StrEnum
from uuid import UUID

class ChatStatus(StrEnum):
    ANSWERED = 'answered'
    NOT_FOUND = 'not_found'
    ESCALATED = 'escalated'
    OFF_TOPIC = 'off_topic'
    CLARIFICATION = 'clarification'
    RESOLVED = 'resolved'

class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=4000, pattern=r"\S")

class SourceResponse(BaseModel):
    title: str
    url: str
    score: float


class ChatResponse(BaseModel):
    choices: list[str] = Field(default_factory=list)
    message_id: UUID | None = None
    message: str | None = None
    status: ChatStatus
    answer: str | None
    sources: list[SourceResponse] = Field(default_factory=list)
    confidence: float | None

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


