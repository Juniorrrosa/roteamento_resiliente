"""Cliente HTTP do Valhalla e logica ERMAC (date_time chuva, payload de rota)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from app.config import settings
from app.schemas import AlagamentoOut

LOG = logging.getLogger(__name__)

# Horarios usados para o switch chuva/seco (ver docs/07-quirks-e-decisoes.md).
# Noite -> Valhalla usa free_flow_speed (sem penalidade). Dia -> constrained_speed (com penalidade).
HOUR_DRY = "03:00"
HOUR_WET = "13:00"


def date_time_for_chuva(chuva: bool) -> dict[str, Any]:
    """Gera o payload `date_time` do Valhalla a partir do flag chuva."""
    hour = HOUR_WET if chuva else HOUR_DRY
    return {"type": 1, "value": f"{date.today().isoformat()}T{hour}"}


def build_route_payload(
    origem: tuple[float, float],
    destino: tuple[float, float],
    chuva: bool,
    excludes: list[AlagamentoOut] | None = None,
    alternates: int = 2,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "locations": [
            {"lat": origem[0], "lon": origem[1]},
            {"lat": destino[0], "lon": destino[1]},
        ],
        "costing": "auto",
        "date_time": date_time_for_chuva(chuva),
        "alternates": alternates,
    }
    if excludes:
        payload["exclude_locations"] = [{"lat": p.lat, "lon": p.lng} for p in excludes]
    return payload


class ValhallaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = base_url or settings.valhalla_url
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def status(self) -> dict[str, Any]:
        r = await self._client.get("/status")
        r.raise_for_status()
        return r.json()

    async def route(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.post("/route", json=payload)
        if r.status_code >= 400:
            LOG.warning("valhalla /route %s: %s", r.status_code, r.text[:200])
            r.raise_for_status()
        return r.json()


# Singleton compartilhado entre requests (instanciado no lifespan do app)
client: ValhallaClient | None = None


def get_client() -> ValhallaClient:
    global client
    if client is None:
        client = ValhallaClient()
    return client
