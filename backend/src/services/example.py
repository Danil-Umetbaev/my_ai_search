from src.exceptions import NoResultFoundException, \
    ExampleNotFoundException, TooMuchResultFoundException, TooMuchExampleFoundException
from src.services.base import BaseService
from src.schemas.example import ExampleCreateSchema, ExamplePatchSchema, ExampleUpdateSchema



class ExampleService(BaseService):

    async def get_examples(
            self,
            **kwargs
    ):
        return await self.db.examples.get_all(**kwargs)

    async def get_example(
            self,
            example_id: int,
    ):
        try:
            return await self.db.examples.get_one(id=example_id)
        except NoResultFoundException:
            raise ExampleNotFoundException

    async def add_example(
            self,
            hotel: ExampleCreateSchema,
    ):
        data = await self.db.examples.add(hotel)
        await self.db.commit()
        return data

    async def update_example(
            self,
            id: int,
            example_data: ExampleUpdateSchema,
    ):
        try:
            await self.db.examples.edit(data=example_data, id=id)
        except NoResultFoundException:
            raise ExampleNotFoundException
        except TooMuchResultFoundException:
            raise TooMuchExampleFoundException
        await self.db.commit()

    async def delete_example(
            self,
            id: int,
    ):
        try:
            await self.db.examples.delete(id=id)
        except NoResultFoundException:
            raise ExampleNotFoundException
        except TooMuchResultFoundException:
            raise TooMuchExampleFoundException
        await self.db.commit()

    async def partial_update_example(
            self,
            id: int,
            example_data: ExamplePatchSchema,
    ):
        try:
            await self.db.examples.edit(data=example_data, id=id, exclude_unset=True)
        except NoResultFoundException:
            raise ExampleNotFoundException
        except TooMuchResultFoundException:
            raise TooMuchExampleFoundException
        await self.db.commit()

