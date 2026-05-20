"""Settings via env (.env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_url: str = "http://localhost:8000"
    cge_url: str = "https://www.cgesp.org/v3/alagamentos.jsp"
    page_load_timeout: int = 30
    element_wait_timeout: int = 15
    http_timeout: float = 30.0
    log_level: str = "INFO"
    headless: bool = True


settings = Settings()
