from uuid import UUID

from src.database import Base
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import VECTOR

class DocumentChunkORM(Base):
    __tablename__ = 'document_chunks'
    document_id: Mapped[UUID] = mapped_column(ForeignKey('documents.id'))
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text())
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1024))
