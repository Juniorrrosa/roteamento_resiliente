"""POST /geocode — Nominatim com cache."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.nominatim import geocode_cached
from app.schemas import GeocodeRequest, GeocodeResponse

router = APIRouter(prefix="/geocode", tags=["geocode"])
LOG = logging.getLogger(__name__)


@router.post("", response_model=GeocodeResponse)
async def geocode(
    payload: GeocodeRequest, session: AsyncSession = Depends(get_session)
) -> GeocodeResponse:
    try:
        lat, lng, display, source = await geocode_cached(
            payload.endereco, session, bairro=payload.bairro, cidade=payload.cidade
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return GeocodeResponse(
        endereco_input=payload.endereco,
        lat=lat,
        lng=lng,
        display_name=display,
        source=source,  # type: ignore[arg-type]
    )
