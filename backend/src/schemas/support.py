from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

TicketStatus = Literal["open", "in_progress", "resolved"]


class SupportMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    request_id: UUID = Field(default_factory=uuid4)
    choice_id: str | None = Field(default=None, max_length=80)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Введите сообщение")
        return value.strip()


class SupportChoice(BaseModel):
    id: str
    label: str


class SupportReply(BaseModel):
    choices: list[SupportChoice] = Field(default_factory=list)
    answer: str
    ticket_id: UUID | None = None
    request_id: UUID
    version: int
    phase: str
    engine: Literal["llm", "rules", "system"]


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TicketStatus
    resolution: str = Field(default="", max_length=4000)
    comment: str = Field(default="", max_length=2000)
    version: int = Field(ge=0)
    assign_to_me: bool = True

    @field_validator("resolution", "comment")
    @classmethod
    def trim(cls, value):
        return value.strip()


class TicketSummary(BaseModel):
    id: UUID
    session_id: UUID
    user_id: int
    details: dict
    status: TicketStatus
    resolution: str
    assigned_to: int | None
    created_at: datetime
    updated_at: datetime
    version: int
