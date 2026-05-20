"""CRUD basico de alagamentos em tempo real (alimentado pelo scraper na Etapa 4)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Alagamento, get_session
from app.schemas import (
    AlagamentoOut,
    SnapshotRequest,
    SnapshotResponse,
)

router = APIRouter(prefix="/alagamentos", tags=["alagamentos"])
LOG = logging.getLogger(__name__)


@router.get("", response_model=list[AlagamentoOut])
async def list_active(session: AsyncSession = Depends(get_session)) -> list[AlagamentoOut]:
    """Lista todos os alagamentos ativos (resolved_at IS NULL)."""
    rows = (
        (await session.scalars(
            select(Alagamento).where(Alagamento.resolved_at.is_(None)).order_by(Alagamento.id)
        ))
        .all()
    )
    return [AlagamentoOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/snapshot", response_model=SnapshotResponse, status_code=200)
async def replace_snapshot(
    payload: SnapshotRequest, session: AsyncSession = Depends(get_session)
) -> SnapshotResponse:
    """Substitui o snapshot ativo atual.

    Logica simples para fase 1: marca todos os ativos como resolvidos
    (resolved_at = now()) e insere os novos pontos como ativos.

    Na fase 4, o scraper podera implementar diff mais inteligente (first_seen/last_seen),
    mas o contrato deste endpoint segue valido.
    """
    now = datetime.now(tz=timezone.utc)

    # 1) marca todos os ativos atuais como resolvidos
    res = await session.execute(
        update(Alagamento)
        .where(Alagamento.resolved_at.is_(None))
        .values(resolved_at=now)
    )
    resolvidos = res.rowcount or 0

    # 2) insere o novo conjunto
    inseridos = 0
    for ponto in payload.pontos:
        session.add(
            Alagamento(
                endereco_raw=ponto.endereco_raw,
                bairro=ponto.bairro,
                referencia=ponto.referencia,
                sentido=ponto.sentido,
                lat=ponto.lat,
                lng=ponto.lng,
            )
        )
        inseridos += 1

    await session.commit()

    ativos = await session.scalar(
        select(func.count(Alagamento.id)).where(Alagamento.resolved_at.is_(None))
    )

    LOG.info("snapshot: %d resolvidos, %d inseridos, %d ativos", resolvidos, inseridos, ativos or 0)
    return SnapshotResponse(inseridos=inseridos, resolvidos=resolvidos, ativos_apos=ativos or 0)


@router.delete("/{alagamento_id}", status_code=204)
async def resolve_one(
    alagamento_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    """Marca manualmente um ponto como resolvido."""
    row = await session.get(Alagamento, alagamento_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alagamento nao encontrado")
    if row.resolved_at is None:
        row.resolved_at = datetime.now(tz=timezone.utc)
        await session.commit()
