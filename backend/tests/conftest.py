from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.api.dependencies import get_db
from src.config import settings
from src.main import app
from src.utils.db import DBManager


TEST_DB_NAME = f"{settings.DB_NAME}_tests"

TEST_DB_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.DB_USER,
    password=settings.DB_PASS,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=TEST_DB_NAME,
)

test_engine = create_async_engine(
    url=TEST_DB_URL, poolclass=NullPool
)

test_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

async def override_get_db():
    async with DBManager(test_session_maker) as db:
        yield db


async def clear_test_data():
    async with test_engine.begin() as connection:
        await connection.execute(
            text(
                """
                TRUNCATE TABLE
                    message_sources,
                    escalations,
                    messages,
                    conversations
                CASCADE
                """
            )
        )

@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    await clear_test_data()

    yield

    await clear_test_data()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = override_get_db


    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url='http://test') as async_client:
        yield async_client


    app.dependency_overrides.clear()
