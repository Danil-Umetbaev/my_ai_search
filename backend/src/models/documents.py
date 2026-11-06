from datetime import datetime

from sqlalchemy import DateTime, String, Text, func, Boolean, text
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class DocumentORM(Base):
    __tablename__ = "documents"
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text(), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    equipment_models: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    software_version: Mapped[str | None] = mapped_column(String(100))
    page_number: Mapped[int | None] = mapped_column()
    images: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
