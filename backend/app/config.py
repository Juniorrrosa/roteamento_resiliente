"""Settings carregadas de env (.env)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://roteamento:changeme@localhost:5432/roteamento",
        description="DSN async do PostGIS",
    )
    valhalla_url: str = "http://localhost:8002"
    nominatim_url: str = "http://localhost:8080"
    ermac_q: float = 10.0
    log_level: str = "INFO"
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
