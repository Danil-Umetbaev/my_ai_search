from datetime import datetime
from pydantic import BaseModel, Field
from enum import StrEnum
from uuid import UUID, uuid4
from src.schemas.support import SupportChoice

class ChatStatus(StrEnum):
    ANSWERED = 'answered'
    NOT_FOUND = 'not_found'
    OFF_TOPIC = 'off_topic'

class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    request_id: UUID = Field(default_factory=uuid4)
    choice_id: str | None = Field(default=None, max_length=80)

class SourceResponse(BaseModel):
    title: str
    url: str
    score: float


class ChatResponse(BaseModel):
    message_id: UUID | None = None
    message: str | None = None
    status: ChatStatus
    answer: str | None
    sources: list[SourceResponse] = Field(default_factory=list)
    confidence: float | None
    choices: list[SupportChoice] = Field(default_factory=list)
    phase: str | None = None

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


