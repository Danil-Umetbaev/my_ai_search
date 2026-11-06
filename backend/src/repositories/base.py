from typing import Sequence, Type

from sqlalchemy import select, insert, update, delete, func
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, SQLAlchemyError

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
    model: Type[Base]
    mapper: Type[DataMapper]

    def __init__(self, session):
        self.session = session

    async def _execute(self, statement):
        try:
            return await self.session.execute(statement)
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise ObjectAlreadyExistsException from error
            raise DataIntegrityException from error
        except SQLAlchemyError as error:
            raise DatabaseException from error

    @staticmethod
    def _values(data: BaseModel | dict, exclude_unset=False):
        return (
            data.model_dump(exclude_unset=exclude_unset)
            if isinstance(data, BaseModel)
            else dict(data)
        )

    async def get_page(self, limit=50, offset=0, *, order_by=None, **filter_by):
        total = (
            await self._execute(
                select(func.count()).select_from(self.model).filter_by(**filter_by)
            )
        ).scalar_one()
        rows = (
            (
                await self._execute(
                    select(self.model)
                    .filter_by(**filter_by)
                    .order_by(*(order_by if order_by is not None else (self.model.id,)))
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

    async def get_all(self, *filters, **filter_by):
        query = select(self.model).filter(*filters).filter_by(**filter_by)
        rows = (await self._execute(query)).scalars().all()
        return [self.mapper.map_to_domain_entity(row) for row in rows]

    async def get_one_or_none(self, *, for_update=False, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        if for_update:
            query = query.with_for_update()
        try:
            row = (await self._execute(query)).scalar_one_or_none()
        except MultipleResultsFound as error:
            raise TooMuchResultFoundException from error
        return self.mapper.map_to_domain_entity(row) if row is not None else None

    async def get_one(self, *, for_update=False, **filter_by):
        result = await self.get_one_or_none(for_update=for_update, **filter_by)
        if result is None:
            raise NoResultFoundException
        return result

    async def add(self, data: BaseModel | dict):
        query = insert(self.model).values(**self._values(data)).returning(self.model)
        row = (await self._execute(query)).scalar_one()
        return self.mapper.map_to_domain_entity(row)

    async def add_bulk(self, data: Sequence[BaseModel]):
        if not data:
            return
        query = insert(self.model).values([self._values(item) for item in data])
        try:
            await self._execute(query)
        except ObjectAlreadyExistsException as error:
            raise DataIntegrityException from error

    async def edit(self, data: BaseModel | dict, exclude_unset=False, **filter_by):
        query = (
            update(self.model)
            .filter_by(**filter_by)
            .values(**self._values(data, exclude_unset))
            .returning(self.model)
            .execution_options(populate_existing=True)
        )
        rows = (await self._execute(query)).scalars().all()
        is_valid_delete_edit(len(rows))
        return self.mapper.map_to_domain_entity(rows[0])

    async def delete(self, *filters, **filter_by):
        query = delete(self.model).filter(*filters).filter_by(**filter_by)
        result = await self._execute(query)
        is_valid_delete_edit(result.rowcount)

    async def delete_all(self):
        await self._execute(delete(self.model))


def is_valid_delete_edit(res: int):
    if res > 1:
        raise TooMuchResultFoundException
    elif res == 0:
        raise NoResultFoundException
