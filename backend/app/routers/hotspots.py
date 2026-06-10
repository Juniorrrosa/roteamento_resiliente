"""GET /hotspots — pontos historicos (pesos estaticos do modelo ERMAC).

Le o relatorio `affected_edges.csv` gerado pelo pipeline (scripts/build_traffic_csvs.py),
que contem as 879 arestas afetadas com seu h(e) real e coordenada correlacionada.
Esses sao os "pesos estaticos" — distintos dos alagamentos em tempo real do CGE.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import Hotspot, HotspotsResponse

router = APIRouter(prefix="/hotspots", tags=["hotspots"])
LOG = logging.getLogger(__name__)

# Cache em memoria: o CSV so muda quando o pipeline roda de novo (raro).
_cache: HotspotsResponse | None = None


def _load() -> HotspotsResponse:
    path = Path(settings.hotspots_csv)
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"relatorio de hotspots nao encontrado em {path}. "
                "Rode scripts/refresh_traffic.py e monte data/ no backend."
            ),
        )

    pontos: list[Hotspot] = []
    max_h = 0
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            try:
                h = int(row["h"])
                lat = float(row["correlated_lat"])
                lng = float(row["correlated_lon"])
            except (KeyError, ValueError):
                continue
            # ignora coordenadas invalidas (0,0 = sem correlacao)
            if lat == 0.0 and lng == 0.0:
                continue
            max_h = max(max_h, h)
            pontos.append(
                Hotspot(
                    lat=lat,
                    lng=lng,
                    h=h,
                    speed_default=int(float(row.get("default_speed_kmh", 0) or 0)),
                    speed_penalizado=int(float(row.get("penalized_speed_kmh", 0) or 0)),
                )
            )

    LOG.info("hotspots carregados: %d (max_h=%d)", len(pontos), max_h)
    return HotspotsResponse(total=len(pontos), max_h=max_h, q=settings.ermac_q, pontos=pontos)


@router.get("", response_model=HotspotsResponse)
async def list_hotspots() -> HotspotsResponse:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache
