from uuid import UUID
from pydantic import BaseModel, Field


class DocumentImage(BaseModel):
    source_url: str
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
    id : UUID
