from uuid import UUID

from pydantic import BaseModel


class VectorSearchResultSchema(BaseModel):
    document_title: str
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    similarity: float


    def __hash__(self):
        return hash(f'{self.chunk_id}{self.document_id}')
