"""Cliente do endpoint /geocode do backend (que usa Nominatim com cache)."""

from __future__ import annotations

import logging

import httpx

LOG = logging.getLogger(__name__)


class GeocodeError(Exception):
    pass


class BackendGeocoder:
    """Wrapper assincrono para POST /geocode."""

    def __init__(self, backend_url: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=backend_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def geocode(
        self, endereco: str, bairro: str | None = None, cidade: str = "São Paulo"
    ) -> tuple[float, float]:
        """Retorna (lat, lng) ou levanta GeocodeError.

        `endereco` deve ser o nome da via (já normalizado); `bairro`/`cidade`
        habilitam a busca estruturada no Nominatim (bem mais precisa que texto livre).
        """
        payload: dict[str, str] = {"endereco": endereco, "cidade": cidade}
        if bairro:
            payload["bairro"] = bairro
        try:
            r = await self._client.post("/geocode", json=payload)
        except httpx.HTTPError as exc:
            raise GeocodeError(f"backend offline: {exc}") from exc

        if r.status_code == 404:
            raise GeocodeError(f"endereco nao encontrado: {endereco!r}")
        if r.status_code >= 400:
            raise GeocodeError(f"backend {r.status_code}: {r.text[:200]}")

        data = r.json()
        return float(data["lat"]), float(data["lng"])
