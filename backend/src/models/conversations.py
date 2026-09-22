from datetime import datetime

from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, func

class ConversationORM(Base):
    __tablename__ = "conversations"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
