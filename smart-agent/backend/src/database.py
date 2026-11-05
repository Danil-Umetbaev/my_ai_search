from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from src.config import settings
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4, UUID
engine = create_async_engine(settings.DB_URL)
engine_null_pool = create_async_engine(settings.DB_URL, poolclass=NullPool)
async_session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)
async_session_maker_null_pool = async_sessionmaker(
    bind=engine_null_pool, expire_on_commit=False
)


class Base(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
