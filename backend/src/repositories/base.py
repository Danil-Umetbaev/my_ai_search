from typing import Sequence, Type
import logging

from asyncpg import UniqueViolationError
from sqlalchemy import select, insert, update, delete, func
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, NoResultFound, SQLAlchemyError

from src.database import Base
from src.exceptions import (
    NoResultFoundException,
    TooMuchResultFoundException,
    ObjectAlreadyExistsException,
    DataIntegrityException,
    DatabaseException,
)

from src.repositories.mappers.base import DataMapper


class BaseRepository:
    model = Type[Base]
    mapper: Type[DataMapper]

    def __init__(self, session):
        self.session = session

    async def execute_admin(self, statement):
        try:
            return await self.session.execute(statement)
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise ObjectAlreadyExistsException from error
            raise DataIntegrityException from error
        except SQLAlchemyError as error:
            raise DatabaseException from error

    async def get_page(self, limit=50, offset=0):
        total = (
            await self.execute_admin(select(func.count()).select_from(self.model))
        ).scalar_one()
        rows = (
            (
                await self.execute_admin(
                    select(self.model)
                    .order_by(self.model.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return {
            "items": [self.mapper.map_to_domain_entity(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_admin(self, object_id, lock=False):
        query = select(self.model).where(self.model.id == object_id)
        if lock:
            query = query.with_for_update()
        row = (await self.execute_admin(query)).scalar_one_or_none()
        if row is None:
            raise NoResultFoundException
        return self.mapper.map_to_domain_entity(row)

    async def create_admin(self, values):
        row = (
            await self.execute_admin(
                insert(self.model).values(**values).returning(self.model)
            )
        ).scalar_one()
        return self.mapper.map_to_domain_entity(row)

    async def update_admin(self, object_id, values):
        row = (
            await self.execute_admin(
                update(self.model)
                .where(self.model.id == object_id)
                .values(**values)
                .returning(self.model)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NoResultFoundException
        return self.mapper.map_to_domain_entity(row)

    async def delete_admin(self, object_id):
        result = await self.execute_admin(
            delete(self.model).where(self.model.id == object_id)
        )
        if result.rowcount == 0:
            raise NoResultFoundException

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
            add_model = (
                insert(self.model).values(**data.model_dump()).returning(self.model)
            )
            result = await self.session.execute(add_model)
            model = result.scalars().first()
            return self.mapper.map_to_domain_entity(model)
        except IntegrityError as ex:
            logging.debug(
                f"Не удалось добавить данные в БД, данные - {data}, тип ошибки - {type(ex.orig.__cause__)=}"
            )
            if isinstance(ex.orig.__cause__, UniqueViolationError):
                raise ObjectAlreadyExistsException
            else:
                logging.error(
                    f"Незнакомая ошибка: данные - {data}, тип ошибки: {type(ex.orig.__cause__)=}"
                )
                raise ex

    async def add_bulk(self, data: Sequence[BaseModel]):
        if not data:
            return
        try:
            add_model = insert(self.model).values([item.model_dump() for item in data])
            await self.session.execute(add_model)
        except IntegrityError as ex:
            raise DataIntegrityException from ex

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
