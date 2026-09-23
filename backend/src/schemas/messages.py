from uuid import UUID
from pydantic import BaseModel
from src.models.enums import Role
from datetime import datetime


class MessageAddRequestSchema(BaseModel):
    conversation_id: UUID
    content: str


class MessageAddSchema(MessageAddRequestSchema):
    role: Role

class MessageSchema(MessageAddSchema):
    id: UUID
    created_at: datetime
