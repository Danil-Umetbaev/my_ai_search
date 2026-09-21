from typing import Annotated

from fastapi import Depends

from src.database import async_session_maker
from src.utils.db import DBManager

async def get_db():
    async with DBManager(async_session_maker) as db:
        yield db


DBDep = Annotated[DBManager, Depends(get_db)]
