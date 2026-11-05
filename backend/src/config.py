from pathlib import Path
from typing import Literal
from sqlalchemy import URL
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DB_NAME: str
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int
    VK_TOKEN: str = ""
    VK_PEER_ID: int = 0
    VK_API_VERSION: str = "5.199"
    VK_GROUP_ID: int = 0
    MODE: Literal["test", "local", "dev", "prod"]
    ENABLE_DOCS: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    AUTH_COOKIE_SECURE: bool = False
    AUTH_TRUSTED_ORIGINS: list[str] = [
        "http://localhost:18081",
        "http://localhost:5173",
    ]
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @property
    def DB_URL(self) -> URL:
        return URL.create(
            drivername='postgresql+asyncpg',
            username=self.DB_USER,
            password=self.DB_PASS,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME
        )


settings = Settings()
