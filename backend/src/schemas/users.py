from src.models.enums import UserRole

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Пароль должен занимать не больше 72 байт")
        return value


class UserRequestAdd(UserLogin):
    role: UserRole


class UserAdd(BaseModel):
    email: EmailStr
    hashed_password: str
    role: UserRole



class User(BaseModel):
    id: int
    email: EmailStr
    role: UserRole


class UserWithHashPassword(User):
    hashed_password: str


class UserDepSchema(BaseModel):
    id: int
    role: UserRole
