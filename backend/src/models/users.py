from sqlalchemy import String

from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from src.models.enums import UserRole

class UsersORM(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(150))


