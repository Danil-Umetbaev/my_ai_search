from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ConversationAddSchema(BaseModel):
    pass

class ConversationSchema(BaseModel):
    id: UUID
    created_at: datetime
