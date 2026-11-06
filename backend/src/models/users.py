from sqlalchemy import String, Boolean, Integer, text

from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from src.models.enums import UserRole


class UsersORM(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    email: Mapped[str] = mapped_column(String(100), unique=True)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(150))
