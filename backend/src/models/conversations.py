from datetime import datetime

from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB

class ConversationORM(Base):
    __tablename__ = "conversations"
    title: Mapped[str] = mapped_column(String(255), nullable=False, server_default="Новый диалог")
    support_state: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
