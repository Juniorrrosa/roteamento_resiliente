"""Cliente do endpoint /alagamentos/snapshot do backend."""

from __future__ import annotations

import logging

import httpx

LOG = logging.getLogger(__name__)


class BackendError(Exception):
    pass


class BackendClient:
    def __init__(self, backend_url: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=backend_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def push_snapshot(self, pontos: list[dict]) -> dict:
        """Faz POST /alagamentos/snapshot. Retorna o body (inseridos/resolvidos/ativos_apos)."""
        try:
            r = await self._client.post("/alagamentos/snapshot", json={"pontos": pontos})
        except httpx.HTTPError as exc:
            raise BackendError(f"backend offline: {exc}") from exc
        if r.status_code >= 400:
            raise BackendError(f"backend {r.status_code}: {r.text[:200]}")
        return r.json()
