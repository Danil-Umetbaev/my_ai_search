from uuid import UUID

from pydantic import BaseModel
from datetime import datetime
from src.models.enums import Status
class EscalationAddSchema(BaseModel):
    conversation_id: UUID
    question: str
    reason: str
    status: Status


class EscalationUpdateSchema(BaseModel):
    status: Status


class EscalationSchema(EscalationAddSchema):
    id: UUID
    created_at: datetime