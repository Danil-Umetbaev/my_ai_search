# ruff: noqa
from logging.config import fileConfig
from sqlalchemy import pool
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import Base
from src.config import settings
from src.models.conversations import ConversationORM
from src.models.documents import DocumentORM
from src.models.escalations import EscalationORM
from src.models.messages import MessageORM
from src.models.document_chunk import DocumentChunkORM
from src.models.message_sources import MessageSourceORM
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", settings.DB_URL.render_as_string(hide_password=False))
# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме с асинхронным движком."""

    # Создаем асинхронный движок напрямую из вашего URL в настройках
    connectable = create_async_engine(
        settings.DB_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Так как Alembic внутри синхронный, мы прокидываем соединение
        # через метод run_sync
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
