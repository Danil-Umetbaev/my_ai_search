from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentImage(BaseModel):
    source_url: str
    local_path: str | None = None
    caption: str = ""
    page_number: int | None = Field(default=None, ge=1)
    position: int = Field(default=0, ge=0)

class DocumentAddSchema(BaseModel):
    source_type: str
    source_url: str
    title: str
    content: str
    checksum: str
    manufacturer: str | None = None
    equipment_models: list[str] = Field(default_factory=list)
    software_version: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    images: list[DocumentImage] = Field(default_factory=list)
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
