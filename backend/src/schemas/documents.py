from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class DocumentAddSchema(BaseModel):
    source_type: str
    source_url: str
    title: str
    content: str
    checksum: str


class DocumentSchema(DocumentAddSchema):
    is_archived: bool = False
    id: UUID


class DocumentSummary(BaseModel):
    is_archived: bool = False
    id: UUID
    title: str
    source_type: str
    source_url: str
    checksum: str
    created_at: datetime
    updated_at: datetime
