from uuid import UUID

from pydantic import BaseModel


class VectorSearchResultSchema(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    similarity: float
    