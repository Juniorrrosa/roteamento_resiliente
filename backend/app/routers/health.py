"""GET /health — verifica os 3 servicos dependentes."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.nominatim import get_client as nominatim_client
from app.schemas import HealthResponse, HealthService
from app.valhalla import get_client as valhalla_client

router = APIRouter(tags=["health"])
LOG = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    services: list[HealthService] = []
    overall = "ok"

    # Postgres
    try:
        await session.execute(text("SELECT 1"))
        services.append(HealthService(name="postgres", status="ok"))
    except Exception as exc:  # noqa: BLE001
        services.append(HealthService(name="postgres", status="down", detail=str(exc)[:200]))
        overall = "down"

    # Valhalla
    try:
        await valhalla_client().status()
        services.append(HealthService(name="valhalla", status="ok"))
    except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001
        services.append(HealthService(name="valhalla", status="down", detail=str(exc)[:200]))
        overall = "down"

    # Nominatim
    try:
        txt = await nominatim_client().status()
        services.append(HealthService(name="nominatim", status="ok", detail=txt))
    except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001
        # Nominatim ausente nao deve derrubar o backend — degrada
        services.append(HealthService(name="nominatim", status="degraded", detail=str(exc)[:200]))
        if overall == "ok":
            overall = "degraded"

    return HealthResponse(status=overall, services=services)
