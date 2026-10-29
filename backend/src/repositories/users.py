from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from pydantic import EmailStr
from src.repositories.mappers.mappers import UserDataMapper
from src.repositories.base import BaseRepository
from src.schemas.users import UserWithHashPassword
from src.models.users import UsersORM
from src.exceptions import NoResultFoundException


class UsersRepository(BaseRepository):
    model = UsersORM
    mapper = UserDataMapper

    async def get_user_with_hashed_password(
        self, email: EmailStr
    ) -> UserWithHashPassword:
        query = select(self.model).filter_by(email=email)
        result = await self.session.execute(query)
        try:
            model = result.scalars().one()
        except NoResultFound:
            raise NoResultFoundException
        return UserWithHashPassword.model_validate(model, from_attributes=True)
