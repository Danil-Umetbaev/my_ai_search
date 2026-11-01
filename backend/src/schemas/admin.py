from typing import Generic, TypeVar
from uuid import UUID
from urllib.parse import urlsplit
import re
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from src.models.enums import UserRole, Status
from src.schemas.users import UserRequestAdd, UserLogin

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class PatchInput(AdminInput):
    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Передайте хотя бы одно поле; null не допускается")
        return self


class DocumentCreate(AdminInput):
    title: str = Field(min_length=1, max_length=512, pattern=r"\S")
    content: str = Field(min_length=1, max_length=300000, pattern=r"\S")
    source_url: str = Field(max_length=2048)

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Нужна HTTP(S)-ссылка без учётных данных")
        return value


class DocumentPatch(PatchInput):
    title: str | None = Field(default=None, min_length=1, max_length=512, pattern=r"\S")
    content: str | None = Field(
        default=None, min_length=1, max_length=300000, pattern=r"\S"
    )


class DocumentImport(AdminInput):
    url: str

    @field_validator("url")
    @classmethod
    def confluence_url(cls, value):
        parsed = urlsplit(value)
        match = re.match(r"^/wiki/spaces/[^/]+/pages/([0-9]+)(?:/|$)", parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "crystals.atlassian.net"
            or not match
        ):
            raise ValueError(
                "Укажите ссылку на страницу базы знаний crystals.atlassian.net"
            )
        return (
            f"https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/{match[1]}"
        )


class ConversationCreate(AdminInput):
    title: str = Field(
        default="Новый диалог", min_length=1, max_length=255, pattern=r"\S"
    )


class ConversationPatch(PatchInput):
    title: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"\S")


class UserCreate(UserRequestAdd):
    email: EmailStr = Field(max_length=100)
    model_config = ConfigDict(extra="forbid")


class UserPatch(PatchInput):
    email: EmailStr | None = Field(default=None, max_length=100)
    role: UserRole | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if value is not None:
            UserLogin.validate_password_bytes(value)
        return value


class EscalationCreate(AdminInput):
    conversation_id: UUID
    question: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    reason: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    status: Status = Status.pending


class EscalationPatch(PatchInput):
    question: str | None = Field(
        default=None, min_length=1, max_length=4000, pattern=r"\S"
    )
    reason: str | None = Field(
        default=None, min_length=1, max_length=4000, pattern=r"\S"
    )
    status: Status | None = None
