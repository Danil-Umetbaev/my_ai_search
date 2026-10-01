from uuid import UUID

from pydantic import BaseModel

class DocumentChunkAddSchema(BaseModel):
    document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float]


class DocumentChunkSchema(DocumentChunkAddSchema):
    id: UUID