"""Cliente do Nominatim com cache no PostGIS."""

from __future__ import annotations

import logging
import unicodedata

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import GeocodeCache

LOG = logging.getLogger(__name__)


def normalize_endereco(s: str) -> str:
    """Normaliza para chave de cache: lowercase, sem acento, sem espacos extras."""
    nfkd = unicodedata.normalize("NFKD", s)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(only_ascii.lower().split()).strip()


class NominatimClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = base_url or settings.nominatim_url
        # Nominatim costuma exigir User-Agent identificavel
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": "roteamento-resiliente/0.1 (backend)"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def status(self) -> str:
        r = await self._client.get("/status")
        r.raise_for_status()
        return r.text.strip()

    async def search(self, endereco: str, limit: int = 1) -> list[dict]:
        """Busca por texto livre (parametro `q`)."""
        r = await self._client.get(
            "/search",
            params={
                "q": endereco,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
                "countrycodes": "br",
            },
        )
        r.raise_for_status()
        return r.json()

    async def search_structured(
        self,
        street: str,
        city: str,
        state: str | None = None,
        limit: int = 1,
    ) -> list[dict]:
        """Busca estruturada (rua + cidade + estado) — mais precisa para
        enderecos informais/sem numero do que o texto livre."""
        params: dict[str, str | int] = {
            "street": street,
            "city": city,
            "format": "json",
            "limit": limit,
            "addressdetails": 1,
            "countrycodes": "br",
        }
        if state:
            params["state"] = state
        r = await self._client.get("/search", params=params)
        r.raise_for_status()
        return r.json()


# Singleton
client: NominatimClient | None = None


def get_client() -> NominatimClient:
    global client
    if client is None:
        client = NominatimClient()
    return client


# =============================================================================
# Geocode com cache
# =============================================================================

async def geocode_cached(
    endereco: str,
    session: AsyncSession,
    bairro: str | None = None,
    cidade: str | None = None,
) -> tuple[float, float, str | None, str]:
    """Retorna (lat, lng, display_name, source).

    source ∈ {'cache', 'nominatim'}.
    Levanta ValueError se Nominatim nao encontrar.

    Se `bairro`/`cidade` forem informados (ex.: chamada do scraper com a via ja
    normalizada), tenta busca ESTRUTURADA primeiro (rua + cidade) e cai para
    texto livre; senao, faz apenas texto livre (chamada tradicional do frontend).
    """
    estruturado = bairro is not None or cidade is not None
    cidade_efetiva = cidade or "São Paulo"

    # chave de cache estavel a partir das entradas
    cache_src = ", ".join(p for p in [endereco, bairro, cidade_efetiva if estruturado else None] if p)
    norm = normalize_endereco(cache_src)

    cached = await session.scalar(
        select(GeocodeCache).where(GeocodeCache.endereco_norm == norm)
    )
    if cached is not None:
        return cached.lat, cached.lng, cached.display_name, "cache"

    client = get_client()
    hit: dict | None = None
    if estruturado:
        # 1) estruturada: rua + cidade + estado
        res = await client.search_structured(
            street=endereco, city=cidade_efetiva, state="São Paulo", limit=1
        )
        # 2) texto livre com bairro
        if not res and bairro:
            res = await client.search(f"{endereco}, {bairro}, {cidade_efetiva}, SP, Brasil", limit=1)
        # 3) texto livre so via + cidade
        if not res:
            res = await client.search(f"{endereco}, {cidade_efetiva}, SP, Brasil", limit=1)
    else:
        res = await client.search(endereco, limit=1)

    if not res:
        raise ValueError(f"Nominatim sem resultado para: {cache_src!r}")
    hit = res[0]
    lat = float(hit["lat"])
    lng = float(hit["lon"])
    display = hit.get("display_name")

    stmt = (
        pg_insert(GeocodeCache)
        .values(
            endereco_norm=norm,
            endereco_raw=cache_src,
            lat=lat,
            lng=lng,
            display_name=display,
            source="nominatim",
        )
        .on_conflict_do_nothing(index_elements=[GeocodeCache.endereco_norm])
    )
    await session.execute(stmt)
    await session.commit()

    return lat, lng, display, "nominatim"
