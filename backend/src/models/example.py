from sqlalchemy import String

from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class ExampleORM(Base):
    __tablename__ = "examples"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    price: Mapped[int]
