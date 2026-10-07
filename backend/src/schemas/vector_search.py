from uuid import UUID

from pydantic import BaseModel


class VectorSearchResultSchema(BaseModel):
    document_title: str
    document_url: str
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    similarity: float