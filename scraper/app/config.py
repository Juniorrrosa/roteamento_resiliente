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

    # --- Modo loop (real-time) ---
    # Cadencia adaptativa: normal, acelerada (ha alagamento ativo) e desacelerada
    # (muito tempo sem nenhum alagamento).
    poll_interval_normal: int = 300      # 5 min — condicao normal
    poll_interval_active: int = 120      # 2 min — ha >=1 alagamento ativo
    poll_interval_quiet: int = 900       # 15 min — apos quiet_after_seconds sem nada
    quiet_after_seconds: int = 3600      # 1h sem alagamentos -> cadencia lenta

    # Retry com backoff exponencial em caso de erro de scraping.
    backoff_base_seconds: int = 30       # 1a falha: ~30s
    backoff_cap_seconds: int = 300       # teto do backoff: 5 min

    # Alerta (log CRITICAL) se o scraping estiver falhando ha mais que isso.
    alert_after_seconds: int = 900       # 15 min

    # Arquivo de heartbeat lido pelo healthcheck do container.
    heartbeat_path: str = "/tmp/scraper_heartbeat"


settings = Settings()
