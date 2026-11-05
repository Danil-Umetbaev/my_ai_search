from fastapi import HTTPException, Response

from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone

from src.config import settings
from src.exceptions import ObjectAlreadyExistsException, UserAlreadyExistsException, NoResultFoundException, UserNotFoundException, InvalidPasswordException
from src.schemas.users import UserRequestAdd, UserAdd, UserLogin
from src.services.base import BaseService


class AuthService(BaseService):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def create_access_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password):
        return self.pwd_context.hash(password)

    def decode_jwt(self, token: str) -> dict:
        try:
            return jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
                 options={"require": ["exp", "user_id", "role"]},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Закончилось действие авторизации, зайдите снова",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Неверный токен",
            )
        except jwt.exceptions.DecodeError:
            raise HTTPException(status_code=401, detail="Неверный токен")




    async def register_user(self, data: UserRequestAdd):
        hashed_password = self.hash_password(data.password)
        new_user_data = UserAdd(
            email=data.email,
            role=data.role,
            hashed_password=hashed_password,
        )
        try:
            await self.db.users.add(new_user_data)
            await self.db.commit()
        except ObjectAlreadyExistsException:
            raise UserAlreadyExistsException


    async def login_user(self, data: UserLogin, response: Response):
        try:
            user = await self.db.users.get_user_with_hashed_password(email=data.email)

        except NoResultFoundException:
            raise UserNotFoundException
        if not self.verify_password(data.password, user.hashed_password):
            raise InvalidPasswordException
        access_token = self.create_access_token(data={"user_id": user.id, 'role': user.role.value})
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            httponly=True,
            secure=settings.AUTH_COOKIE_SECURE,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"



    async def get_me(self, user_id: int):
        user = await self.db.users.get_one_or_none(id=user_id)

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Пользователь не найден. Войдите снова.",
            )

        return user


    async def logout_user(self, response: Response):
        response.delete_cookie(
            key="access_token",
            path="/",
            httponly=True,
            secure=settings.AUTH_COOKIE_SECURE,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
