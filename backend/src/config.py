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
    MODE: Literal["test", "local", "dev", "prod"]

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
