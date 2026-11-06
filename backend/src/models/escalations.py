from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, DateTime, Text, func, String, CheckConstraint
from src.database import Base
from src.models.enums import Status


class EscalationORM(Base):
    __tablename__ = "escalations"
    __table_args__ = (
        CheckConstraint(
            "work_status IN ('new', 'in_progress', 'resolved', 'closed')",
            name="ck_escalations_work_status",
        ),
    )
    work_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="new"
    )
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"))
    question: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[Status] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
