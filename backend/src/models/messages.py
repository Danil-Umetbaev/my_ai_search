from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from src.models.enums import Role
from src.database import Base




class MessageORM(Base):
    __tablename__ = "messages"
    response_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('conversations.id'))
    role: Mapped[Role] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )