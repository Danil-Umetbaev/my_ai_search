from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class SupportSessionORM(Base):
    __tablename__ = "support_sessions"
    __table_args__ = (Index("ix_support_sessions_user", "user_id", "created_at"),)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    state: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    history: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    ticket_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("support_tickets.id", name="support_session_ticket", use_alter=True)
    )
    version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SupportTicketORM(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved')",
            name="support_tickets_status_check",
        ),
        Index("support_tickets_created", text("created_at DESC")),
        Index("ix_support_tickets_user_status", "user_id", "status"),
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_sessions.id"), unique=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    details: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    resolution: Mapped[str] = mapped_column(Text, server_default="")
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SupportTicketEventORM(Base):
    __tablename__ = "support_ticket_events"
    __table_args__ = (
        Index("ix_support_ticket_events_ticket", "ticket_id", "created_at"),
    )
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE")
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
