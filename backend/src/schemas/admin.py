from typing import Generic, TypeVar, Literal
from uuid import UUID
from urllib.parse import urlsplit
import re
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from src.models.enums import UserRole

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


class UserPatch(PatchInput):
    role: UserRole | None = None
    is_active: bool | None = None


class EscalationPatch(AdminInput):
    work_status: Literal["new", "in_progress", "resolved", "closed"] | None = None
    assigned_to: int | None = None
    resolution: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("Нет изменений")
        if any(
            getattr(self, key) is None
            for key in self.model_fields_set - {"assigned_to"}
        ):
            raise ValueError("Поле не может быть пустым")
        return self
