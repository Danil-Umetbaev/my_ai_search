from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, DateTime, Text, func
from src.database import Base
from src.models.enums import Status




class EscalationORM(Base):
    __tablename__ = "escalations"
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('conversations.id'))
    question: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[Status] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
