from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class ConversationAddSchema(BaseModel):
    pass

class ConversationSchema(BaseModel):
    id: UUID

