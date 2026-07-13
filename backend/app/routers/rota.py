"""POST /rota — orquestrador ERMAC: geocoda, le alagamentos, chama Valhalla."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Alagamento, get_session
from app.nominatim import geocode_cached
from app.schemas import (
    Location,
    RotaRequest,
    RotaResponse,
    RotaTrecho,
)
from app.schemas import AlagamentoOut
from app.valhalla import build_route_payload, get_client as valhalla_client

router = APIRouter(prefix="/rota", tags=["rota"])
LOG = logging.getLogger(__name__)


def _is_no_path(response: httpx.Response) -> bool:
    """True se o Valhalla respondeu 442 (No path could be found)."""
    try:
        return response.json().get("error_code") == 442
    except Exception:
        return False


async def _resolve_location(loc: Location, session: AsyncSession) -> tuple[float, float]:
    if loc.lat is not None and loc.lng is not None:
        return loc.lat, loc.lng
    if not loc.endereco:
        raise HTTPException(status_code=400, detail="location sem coords nem endereco")
    try:
        lat, lng, _display, _src = await geocode_cached(loc.endereco, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return lat, lng


def _trip_to_trecho(trip: dict, tipo: str) -> RotaTrecho:
    summary = trip["summary"]
    legs = trip.get("legs", [])
    shape = legs[0]["shape"] if legs else ""
    maneuvers = [m for leg in legs for m in leg.get("maneuvers", [])]
    return RotaTrecho(
        tipo=tipo,  # type: ignore[arg-type]
        length_km=float(summary["length"]),
        time_seconds=float(summary["time"]),
        shape=shape,
        maneuvers=maneuvers,
    )


@router.post("", response_model=RotaResponse)
async def calcular_rota(
    payload: RotaRequest, session: AsyncSession = Depends(get_session)
) -> RotaResponse:
    # 1. resolve origem/destino (coords diretas ou geocoding)
    origem = await _resolve_location(payload.origem, session)
    destino = await _resolve_location(payload.destino, session)

    # 2. carrega alagamentos ativos (somente se for evitar)
    if payload.evitar_alagamentos:
        ativos_db = (
            await session.scalars(
                select(Alagamento).where(Alagamento.resolved_at.is_(None))
            )
        ).all()
        excludes = [AlagamentoOut.model_validate(r, from_attributes=True) for r in ativos_db]
    else:
        excludes = []

    # 3. monta payload Valhalla
    body = build_route_payload(
        origem=origem,
        destino=destino,
        chuva=payload.chuva,
        excludes=excludes,
        alternates=payload.alternates,
    )

    # 4. chama Valhalla
    try:
        result = await valhalla_client().route(body)
    except httpx.HTTPStatusError as exc:
        # 442 = "No path could be found": resposta legitima quando os alagamentos
        # bloqueiam todos os caminhos (ou prendem origem/destino). Nao e erro de
        # servidor — devolvemos rota vazia marcada como bloqueada.
        if _is_no_path(exc.response):
            return RotaResponse(
                modo="chuva" if payload.chuva else "seco",
                alagamentos_evitados=len(excludes),
                rotas=[],
                origem_usada=origem,
                destino_usado=destino,
                bloqueada=True,
            )
        raise HTTPException(status_code=502, detail=f"Valhalla: {exc.response.text[:200]}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Valhalla offline: {exc}") from exc

    # 5. formata resposta
    rotas: list[RotaTrecho] = [_trip_to_trecho(result["trip"], "principal")]
    for alt in result.get("alternates", []) or []:
        rotas.append(_trip_to_trecho(alt["trip"], "alternativa"))

    return RotaResponse(
        modo="chuva" if payload.chuva else "seco",
        alagamentos_evitados=len(excludes),
        rotas=rotas,
        origem_usada=origem,
        destino_usado=destino,
    )
