"""Testes das funcoes puras de cadencia/backoff e do orquestrador run_loop."""

from __future__ import annotations

import asyncio

from app.config import Settings
from app.loop import backoff_seconds, next_interval_seconds, run_loop

CFG = Settings()  # defaults: normal=300, active=120, quiet=900, quiet_after=3600


# ---------------------------------------------------------------------------
# next_interval_seconds
# ---------------------------------------------------------------------------

def _interval(found, since):
    return next_interval_seconds(
        found, since,
        normal=CFG.poll_interval_normal,
        active=CFG.poll_interval_active,
        quiet=CFG.poll_interval_quiet,
        quiet_after=CFG.quiet_after_seconds,
    )


def test_intervalo_ativo_quando_ha_alagamento():
    # achou alagamento -> cadencia acelerada, independente do tempo sem chuva
    assert _interval(found=1, since=0) == 120
    assert _interval(found=5, since=99999) == 120


def test_intervalo_normal_sem_alagamento_recente():
    # 0 alagamentos, mas faz pouco tempo desde o ultimo -> normal
    assert _interval(found=0, since=0) == 300
    assert _interval(found=0, since=3599) == 300


def test_intervalo_quiet_apos_uma_hora_sem_nada():
    # 0 alagamentos e >= 1h sem nenhum -> cadencia lenta
    assert _interval(found=0, since=3600) == 900
    assert _interval(found=0, since=10000) == 900


# ---------------------------------------------------------------------------
# backoff_seconds
# ---------------------------------------------------------------------------

def test_backoff_exponencial_com_teto():
    base, cap = CFG.backoff_base_seconds, CFG.backoff_cap_seconds  # 30, 300
    assert backoff_seconds(0, base=base, cap=cap) == 0
    assert backoff_seconds(1, base=base, cap=cap) == 30
    assert backoff_seconds(2, base=base, cap=cap) == 60
    assert backoff_seconds(3, base=base, cap=cap) == 120
    assert backoff_seconds(4, base=base, cap=cap) == 240
    assert backoff_seconds(5, base=base, cap=cap) == 300   # teto
    assert backoff_seconds(10, base=base, cap=cap) == 300  # continua no teto


# ---------------------------------------------------------------------------
# run_loop (com dependencias injetadas, sem rede/Selenium)
# ---------------------------------------------------------------------------

def test_run_loop_acelera_quando_acha_alagamento():
    """1o ciclo acha 2 alagamentos -> proximo sleep deve ser o intervalo ativo."""
    sleeps: list[float] = []
    heartbeats: list[float] = []
    clock = {"t": 1000.0}

    async def fake_pipeline():
        return {"total_parsed": 2, "pushed": True}

    async def fake_sleep(s):
        sleeps.append(s)

    asyncio.run(run_loop(
        CFG,
        pipeline_fn=fake_pipeline,
        sleep_fn=fake_sleep,
        clock_fn=lambda: clock["t"],
        now_fn=lambda: 42.0,
        heartbeat_fn=lambda path, epoch: heartbeats.append(epoch),
        max_iterations=1,
    ))

    assert sleeps == [120]            # cadencia ativa
    assert heartbeats == [42.0]       # heartbeat escrito no ciclo ok


def test_run_loop_backoff_em_falha():
    """Pipeline sempre falha -> sleeps seguem o backoff exponencial, sem heartbeat."""
    sleeps: list[float] = []
    heartbeats: list[float] = []

    async def fake_pipeline():
        raise RuntimeError("selenium morreu")

    async def fake_sleep(s):
        sleeps.append(s)

    asyncio.run(run_loop(
        CFG,
        pipeline_fn=fake_pipeline,
        sleep_fn=fake_sleep,
        clock_fn=lambda: 0.0,
        now_fn=lambda: 1.0,
        heartbeat_fn=lambda path, epoch: heartbeats.append(epoch),
        max_iterations=3,
    ))

    assert sleeps == [30, 60, 120]    # backoff exponencial
    assert heartbeats == []           # nenhum heartbeat em ciclo que falhou
