from uuid import UUID
from pydantic import BaseModel
from src.models.enums import Role
from datetime import datetime



class MessageAddSchema(BaseModel):
    conversation_id: UUID
    role: Role
    content: str
    created_at: datetime


class MessageSchema(MessageAddSchema):
    id: UUID