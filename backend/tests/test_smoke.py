"""Smoke tests sem dependencia de servicos externos (Valhalla/Nominatim/Postgres).

Para testar contra os servicos reais, ver scripts/smoke_backend.py.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.schemas import GeocodeRequest, Location, RotaRequest
from app.valhalla import build_route_payload, date_time_for_chuva


def test_date_time_for_chuva_off() -> None:
    payload = date_time_for_chuva(False)
    assert payload["type"] == 1
    assert payload["value"].endswith("T03:00")
    assert payload["value"].startswith(date.today().isoformat())


def test_date_time_for_chuva_on() -> None:
    payload = date_time_for_chuva(True)
    assert payload["value"].endswith("T13:00")


def test_build_route_payload_basic() -> None:
    body = build_route_payload(
        origem=(-23.5, -46.6),
        destino=(-23.55, -46.65),
        chuva=False,
        excludes=None,
        alternates=2,
    )
    assert body["locations"][0]["lat"] == -23.5
    assert body["locations"][1]["lon"] == -46.65
    assert body["costing"] == "auto"
    assert body["alternates"] == 2
    assert body["date_time"]["value"].endswith("T03:00")
    assert "exclude_locations" not in body


def test_build_route_payload_with_excludes() -> None:
    from app.schemas import AlagamentoOut
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    exc = [
        AlagamentoOut(id=1, lat=-23.56, lng=-46.61, first_seen=now, last_seen=now),
        AlagamentoOut(id=2, lat=-23.57, lng=-46.62, first_seen=now, last_seen=now),
    ]
    body = build_route_payload(
        origem=(-23.5, -46.6),
        destino=(-23.55, -46.65),
        chuva=True,
        excludes=exc,
        alternates=0,
    )
    assert body["date_time"]["value"].endswith("T13:00")
    assert body["exclude_locations"] == [
        {"lat": -23.56, "lon": -46.61},
        {"lat": -23.57, "lon": -46.62},
    ]


def test_location_requires_coords_or_endereco() -> None:
    with pytest.raises(ValueError):
        Location()


def test_location_accepts_coords() -> None:
    loc = Location(lat=-23.5, lng=-46.6)
    assert loc.lat == -23.5


def test_location_accepts_endereco() -> None:
    loc = Location(endereco="Av Paulista 1000")
    assert loc.endereco == "Av Paulista 1000"


def test_rota_request_validates() -> None:
    req = RotaRequest(
        origem=Location(lat=-23.5, lng=-46.6),
        destino=Location(endereco="Sé"),
        chuva=True,
        alternates=3,
    )
    assert req.alternates == 3
    assert req.chuva is True


def test_geocode_request_minlen() -> None:
    with pytest.raises(Exception):
        GeocodeRequest(endereco="x")  # min_length=3
