from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://admin:admin123@localhost:5432/happy_sandwich"
    access_key: str | None = None
    allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "https://happy-sandwich-front-3lw8oqjda-eggblackgits-projects.vercel.app", "https://happy-sandwich-front.vercel.app"]
    line_channel_access_token: str | None = None
    line_target_ids: list[str] = Field(default_factory=list)

    class Config:
        env_file = ".env"

    @field_validator("line_target_ids", mode="before")
    @classmethod
    def split_line_targets(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if value is None:
            return []
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
