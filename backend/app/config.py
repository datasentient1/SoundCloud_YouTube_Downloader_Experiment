from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Artist Catalog Downloader"
    app_origin: str = "http://localhost:8000"
    database_path: Path = Path("data/app.db")
    downloads_dir: Path = Path("data/downloads")
    jwt_secret: str = "change-me-before-deploying"
    jwt_algorithm: str = "HS256"
    token_minutes: int = 60 * 24 * 14
    max_concurrent_jobs: int = 2
    job_retention_hours: int = 24

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    return settings
