from uuid import UUID
from pydantic import BaseModel

class DocumentAddSchema(BaseModel):
    source_type: str
    source_url: str
    title: str
    content: str
    checksum: str
class DocumentSchema(DocumentAddSchema):
    id : UUID