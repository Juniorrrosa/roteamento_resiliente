"""Popula o PostGIS com alagamentos FICTICIOS para a demo (docs/demo.md).

Insere, via o mesmo endpoint do scraper (POST /alagamentos/snapshot):
  - 2 pontos bloqueando a travessia do Rio Tiete na rota Casa Verde -> Republica
    (Demo 1 -- restricao dura, desvio grande e visivel)
  - alguns marcadores extras em locais classicos de alagamento (geocodados)

Pensado para rodar DENTRO do container `backend` (tem Python 3.12 + rede interna):

    docker exec -i backend python - < scripts/seed_demo_alagamentos.py

Os pontos ficam rotulados com "FICTICIO-demo" no endereco, para distinguir do dado real.
Para limpar depois: POST /alagamentos/snapshot com {"pontos": []}.
"""

from __future__ import annotations

import json
import os
import urllib.request

VALHALLA = os.environ.get("VALHALLA_URL", "http://valhalla:8002")
BACKEND = os.environ.get("BACKEND_SELF_URL", "http://localhost:8000")

# rota base da Demo 1 (enderecos que geocodam de forma estavel)
ORIGEM = {"lat": -23.50262, "lon": -46.65604}   # Av. Casa Verde, 1500
DESTINO = {"lat": -23.54317, "lon": -46.64252}  # Praca da Republica


def call(url: str, body: dict | None = None) -> dict:
    if body is None:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def geocode(endereco: str) -> tuple[float, float] | None:
    try:
        r = call(f"{BACKEND}/geocode", {"endereco": endereco})
        return r["lat"], r["lng"]
    except Exception:
        return None


def decode_polyline(s: str, precision: int = 6) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    index = lat = lng = 0
    factor = 10 ** precision
    while index < len(s):
        for k in range(2):
            shift = result = 0
            while True:
                b = ord(s[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if (result & 1) else (result >> 1)
            if k == 0:
                lat += d
            else:
                lng += d
        coords.append((lat / factor, lng / factor))
    return coords


def main() -> int:
    # 1. rota base + pontos que bloqueiam a travessia
    base = call(
        f"{VALHALLA}/route",
        {
            "locations": [ORIGEM, DESTINO],
            "costing": "auto",
            "date_time": {"type": 1, "value": "2026-06-19T13:00"},
        },
    )
    pts = decode_polyline(base["trip"]["legs"][0]["shape"], 6)

    # busca o ponto ao longo da rota cujo bloqueio causa o maior desvio
    best = None
    for frac in (f / 100 for f in range(30, 70, 3)):
        la, ln = pts[int(len(pts) * frac)]
        r = call(
            f"{VALHALLA}/route",
            {
                "locations": [ORIGEM, DESTINO],
                "costing": "auto",
                "date_time": {"type": 1, "value": "2026-06-19T13:00"},
                "exclude_locations": [{"lat": la, "lon": ln}],
            },
        )
        length = r["trip"]["summary"]["length"]
        if best is None or length > best[0]:
            best = (length, la, ln)

    _, bla, bln = best
    i_best = min(range(len(pts)), key=lambda i: (pts[i][0] - bla) ** 2 + (pts[i][1] - bln) ** 2)
    travessia = [pts[i_best], pts[min(i_best + 3, len(pts) - 1)]]

    pontos: list[dict] = []
    for j, (la, ln) in enumerate(travessia, start=1):
        pontos.append(
            {
                "endereco_raw": f"Ponte/Av. sobre o Rio Tiete (FICTICIO-demo {j})",
                "bairro": "Casa Verde / Bom Retiro",
                "referencia": "ponte alagada - intransitavel",
                "sentido": "centro",
                "lat": round(la, 6),
                "lng": round(ln, 6),
            }
        )

    # 2. marcadores extras (so visuais) em locais classicos de alagamento
    extras = [
        ("Avenida Nove de Julho, Sao Paulo", "Bela Vista"),
        ("Avenida Reboucas, Sao Paulo", "Pinheiros"),
        ("Praca Charles Miller, Pacaembu, Sao Paulo", "Pacaembu"),
        ("Largo do Arouche, Sao Paulo", "Republica"),
        ("Avenida do Estado, Sao Paulo", "Bras"),
        ("Avenida Pacaembu, Sao Paulo", "Agua Branca"),
    ]
    for endereco, bairro in extras:
        g = geocode(endereco)
        if g:
            pontos.append(
                {
                    "endereco_raw": endereco,
                    "bairro": bairro,
                    "referencia": "bolsao d'agua",
                    "sentido": None,
                    "lat": g[0],
                    "lng": g[1],
                }
            )

    # 3. publica o snapshot (igual ao scraper)
    resp = call(f"{BACKEND}/alagamentos/snapshot", {"pontos": pontos})
    print(f"snapshot publicado: {json.dumps(resp)}")
    print(f"total de pontos ficticios inseridos: {len(pontos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
