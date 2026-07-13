"""DTOs Pydantic dos endpoints. Request e response shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Geocode
# ============================================================================

class GeocodeRequest(BaseModel):
    endereco: str = Field(..., min_length=3, examples=["Av Paulista 1000, Sao Paulo"])


class GeocodeResponse(BaseModel):
    endereco_input: str
    lat: float
    lng: float
    display_name: str | None = None
    source: Literal["nominatim", "cache"]


# ============================================================================
# Alagamentos
# ============================================================================

class AlagamentoIn(BaseModel):
    """Payload de um ponto vindo do scraper."""
    endereco_raw: str | None = None
    bairro: str | None = None
    referencia: str | None = None
    sentido: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class AlagamentoOut(AlagamentoIn):
    id: int
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None = None


class SnapshotRequest(BaseModel):
    """Snapshot completo do CGE — substitui o conjunto ativo atual."""
    pontos: list[AlagamentoIn] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    inseridos: int
    resolvidos: int
    ativos_apos: int


# ============================================================================
# Rota
# ============================================================================

class Location(BaseModel):
    """Pode ser fornecido como (lat,lng) OU como endereco (sera geocodificado)."""
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    endereco: str | None = None

    @model_validator(mode="after")
    def either_coords_or_endereco(self) -> Location:
        has_coords = self.lat is not None and self.lng is not None
        has_end = bool(self.endereco)
        if not (has_coords or has_end):
            raise ValueError("forneca (lat, lng) ou endereco")
        if has_coords and has_end:
            # ambos fornecidos: prioriza coords, ignora endereco
            pass
        return self


class RotaRequest(BaseModel):
    origem: Location
    destino: Location
    chuva: bool = Field(
        default=False,
        description="Se True, aplica peso historico h(e)/Q via date_time diurno",
    )
    evitar_alagamentos: bool = Field(
        default=True,
        description="Se True, exclui (b(e)=inf) os alagamentos ativos do CGE da rota",
    )
    alternates: int = Field(default=2, ge=0, le=3)


class RotaTrecho(BaseModel):
    tipo: Literal["principal", "alternativa"]
    length_km: float
    time_seconds: float
    shape: str = Field(..., description="Encoded polyline (precision 1e-6)")
    maneuvers: list[dict] = Field(default_factory=list)


class RotaResponse(BaseModel):
    modo: Literal["seco", "chuva"]
    alagamentos_evitados: int
    rotas: list[RotaTrecho]
    origem_usada: tuple[float, float]
    destino_usado: tuple[float, float]
    bloqueada: bool = Field(
        default=False,
        description="True se nao ha rota possivel evitando os alagamentos ativos (Valhalla 442)",
    )


# ============================================================================
# Hotspots historicos (pesos estaticos do modelo ERMAC)
# ============================================================================

class Hotspot(BaseModel):
    lat: float
    lng: float
    h: int = Field(..., description="Severidade: nº de ocorrências históricas na aresta")
    speed_default: int = Field(..., description="Velocidade livre da via (km/h)")
    speed_penalizado: int = Field(..., description="Velocidade efetiva sob chuva (km/h)")


class HotspotsResponse(BaseModel):
    total: int
    max_h: int
    q: float
    pontos: list[Hotspot]


# ============================================================================
# Health
# ============================================================================

class HealthService(BaseModel):
    name: str
    status: Literal["ok", "degraded", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    services: list[HealthService]
