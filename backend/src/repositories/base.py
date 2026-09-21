from typing import Sequence, Type
import logging

from asyncpg import UniqueViolationError
from sqlalchemy import select, insert, update, delete
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, NoResultFound

from src.database import Base
from src.exceptions import NoResultFoundException, TooMuchResultFoundException, ObjectAlreadyExistsException
from src.repositories.mappers.base import DataMapper


class BaseRepository:
    model = Type[Base]
    mapper: Type[DataMapper]

    def __init__(self, session):
        self.session = session

    async def get_all(self, *filter, **kwargs):
        query = select(self.model)
        result = await self.session.execute(query)
        result = result.scalars().all()
        if result is None:
            return None
        return [self.mapper.map_to_domain_entity(obj) for obj in result]

    async def get_one_or_none(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        obj = result.scalars().one_or_none()
        if obj is None:
            return None
        return self.mapper.map_to_domain_entity(obj)

    async def get_one(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        try:
            obj = result.scalars().one()
        except NoResultFound:
            raise NoResultFoundException
        return self.mapper.map_to_domain_entity(obj)

    async def add(self, data: BaseModel):
        try:
            add_model = insert(self.model).values(**data.model_dump()).returning(self.model)
            result = await self.session.execute(add_model)
            model = result.scalars().first()
            return self.mapper.map_to_domain_entity(model)
        except IntegrityError as ex:
            logging.debug(
                f'Не удалось добавить данные в БД, данные - {data}, тип ошибки - {type(ex.orig.__cause__)=}'
            )
            if isinstance(ex.orig.__cause__, UniqueViolationError):
                raise ObjectAlreadyExistsException
            else:
                logging.error(f'Незнакомая ошибка: данные - {data}, тип ошибки: {type(ex.orig.__cause__)=}')
                raise ex



    async def add_bulk(self, data: Sequence[BaseModel]):
        try:
            add_model = insert(self.model).values([item.model_dump() for item in data])
            await self.session.execute(add_model)
        except IntegrityError as ex:
            raise NoResultFoundException

    async def edit(self, data: BaseModel, exclude_unset: bool = False, **filter_by):
        edit_model = (
            update(self.model)
            .filter_by(**filter_by)
            .values(**data.model_dump(exclude_unset=exclude_unset))
        )
        result = await self.session.execute(edit_model)
        is_valid_delete_edit(result.rowcount)

    async def delete(self, *filter, **filter_by):
        delete_model = delete(self.model).filter(*filter).filter_by(**filter_by)
        res = await self.session.execute(delete_model)
        is_valid_delete_edit(res.rowcount)

    async def delete_all(self):
        query = delete(self.model)
        await self.session.execute(query)


def is_valid_delete_edit(res: int):
    if res > 1:
        raise TooMuchResultFoundException
    elif res == 0:
        raise NoResultFoundException
