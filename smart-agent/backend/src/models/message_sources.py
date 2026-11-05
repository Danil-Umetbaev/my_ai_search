from uuid import UUID
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

class MessageSourceORM(Base):
    __tablename__ = 'message_sources'

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey('messages.id'),
        nullable=False
    )

    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey('document_chunks.id'),
        nullable=False
    )
    relevance_score: Mapped[float] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint(
            'message_id',
            'chunk_id',
            name='uq_message_chunk'
        ),
    )