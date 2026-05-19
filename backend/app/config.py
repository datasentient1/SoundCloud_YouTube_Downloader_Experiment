from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Playlist MP3 Downloader"
    app_origin: str = "http://localhost:8000"
    database_path: Path = Path("data/app.db")
    downloads_dir: Path = Path("data/downloads")
    max_concurrent_jobs: int = 2
    job_retention_hours: int = 24
    ytdlp_cookies_path: Path | None = None
    ytdlp_cookies: str | None = None
    ytdlp_impersonate: str | None = "chrome"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    return settings
