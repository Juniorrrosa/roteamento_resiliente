"""Modo loop (real-time): roda o pipeline em cadencia adaptativa.

Duas partes:
- Funcoes PURAS de decisao (`next_interval_seconds`, `backoff_seconds`) — sem I/O,
  faceis de testar.
- Orquestrador `run_loop` — chama o pipeline, aplica a cadencia, escreve heartbeat
  e trata erros com backoff. Recebe dependencias injetaveis para teste.

Cadencia (defaults em config.Settings):
- achou >=1 alagamento          -> poll_interval_active   (2 min)
- 0 alagamentos, mas < 1h sem   -> poll_interval_normal   (5 min)
- 0 alagamentos e >= 1h sem     -> poll_interval_quiet    (15 min)

Erro de scraping/push -> backoff exponencial (base 30s, teto 5 min). Se falhar por
mais que alert_after_seconds, emite log CRITICAL (periodo critico).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from app.config import Settings, settings
from app.pipeline import run_pipeline

LOG = logging.getLogger(__name__)


def next_interval_seconds(
    found_count: int,
    seconds_since_last_flood: float,
    *,
    normal: int,
    active: int,
    quiet: int,
    quiet_after: int,
) -> int:
    """Segundos ate o proximo ciclo, dada a situacao atual. Funcao pura."""
    if found_count > 0:
        return active
    if seconds_since_last_flood >= quiet_after:
        return quiet
    return normal


def backoff_seconds(consecutive_failures: int, *, base: int, cap: int) -> int:
    """Backoff exponencial: base * 2^(n-1), limitado a cap. Funcao pura."""
    if consecutive_failures <= 0:
        return 0
    return min(cap, base * (2 ** (consecutive_failures - 1)))


def _write_heartbeat(path: str, epoch: float) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(str(epoch))
    except OSError as exc:  # nao derruba o loop por causa do heartbeat
        LOG.warning("nao consegui escrever heartbeat em %s: %s", path, exc)


async def run_loop(
    cfg: Settings = settings,
    *,
    pipeline_fn: Callable[[], Awaitable[dict]] = run_pipeline,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock_fn: Callable[[], float] = time.monotonic,
    now_fn: Callable[[], float] = time.time,
    heartbeat_fn: Callable[[str, float], None] = _write_heartbeat,
    max_iterations: int | None = None,
) -> None:
    """Loop principal do worker real-time.

    `max_iterations` limita o numero de ciclos (usado em teste); None = infinito.
    As dependencias (`pipeline_fn`, `sleep_fn`, clocks, heartbeat) sao injetaveis
    para permitir teste deterministico sem rede/Selenium.
    """
    LOG.info(
        "iniciando loop real-time (normal=%ds, ativo=%ds, quiet=%ds apos %dmin sem alagamentos)",
        cfg.poll_interval_normal, cfg.poll_interval_active,
        cfg.poll_interval_quiet, cfg.quiet_after_seconds // 60,
    )

    last_flood_at = clock_fn()      # assume "recente" no start (comeca em cadencia normal)
    consecutive_failures = 0
    first_failure_at: float | None = None
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            result = await pipeline_fn()
        except Exception as exc:  # scraping/geocode/push falhou
            consecutive_failures += 1
            now = clock_fn()
            if first_failure_at is None:
                first_failure_at = now
            failing_for = now - first_failure_at
            LOG.error("ciclo falhou (%dx consecutivas): %s", consecutive_failures, exc)
            if failing_for >= cfg.alert_after_seconds:
                LOG.critical(
                    "ALERTA: scraper falhando ha %.0f min — periodo potencialmente critico!",
                    failing_for / 60,
                )
            interval = backoff_seconds(
                consecutive_failures, base=cfg.backoff_base_seconds, cap=cfg.backoff_cap_seconds
            )
            LOG.info("backoff: proximo ciclo em %ds", interval)
            await sleep_fn(interval)
            continue

        # sucesso
        consecutive_failures = 0
        first_failure_at = None
        found = int(result.get("total_parsed", 0) or 0)
        now = clock_fn()
        if found > 0:
            last_flood_at = now
        heartbeat_fn(cfg.heartbeat_path, now_fn())

        since = now - last_flood_at
        interval = next_interval_seconds(
            found, since,
            normal=cfg.poll_interval_normal,
            active=cfg.poll_interval_active,
            quiet=cfg.poll_interval_quiet,
            quiet_after=cfg.quiet_after_seconds,
        )
        LOG.info(
            "ciclo ok: %d alagamentos, pushed=%s. Proximo em %ds",
            found, result.get("pushed"), interval,
        )
        await sleep_fn(interval)
