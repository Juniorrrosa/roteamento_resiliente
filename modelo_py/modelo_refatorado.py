"""
exemplo_uso.py
--------------
Demonstração do modelo de roteamento resiliente a alagamentos.
Gera três mapas HTML usando Folium:
    1. exemplo_mapa.html             — rotas sem buffer visual
    2. exemplo_mapa_buffer.html      — rotas com raio de 200 m nos pontos críticos
    3. exemplo_mapa_historico.html   — mapa de calor do histórico de alagamentos
"""

from __future__ import annotations

import os

import folium
from folium.plugins import HeatMap

from flood_routing import Coordinate, FloodRouting, ModelType, RouteResult

# ---------------------------------------------------------------------------
# Configuração da área de estudo
# ---------------------------------------------------------------------------

BBOX = dict(north=-23.510, south=-23.610, east=-46.560, west=-46.650)

HISTORY_SHP = os.path.join(os.path.dirname(__file__), "Alag-Inun_2015-2025.shp")

CALIBRATION_Q = 10.0

# ---------------------------------------------------------------------------
# Pontos de origem, destino e alagamentos ativos
# ---------------------------------------------------------------------------

ORIGIN: Coordinate = (-23.57035611475849, -46.60791785483021)
DESTINATION: Coordinate = (-23.56785094906498, -46.604854772077694)

# Pontos de alagamento em tempo real (lat, lon).
# Em produção, esses pontos virão do scraper do CGE.
CURRENT_FLOODS: list[Coordinate] = [
    (-23.56821, -46.60765),
]

RAINING: bool = True

# ---------------------------------------------------------------------------
# Configuração visual das rotas
# ---------------------------------------------------------------------------

ROUTE_STYLES: dict[ModelType, dict] = {
    ModelType.STANDARD:       {"color": "gray",   "label": "Padrão (sem penalidades)"},
    ModelType.HISTORICAL_ONLY: {"color": "blue",   "label": "Apenas histórico"},
    ModelType.REAL_TIME_ONLY:  {"color": "orange", "label": "Apenas tempo real"},
    ModelType.PROPOSED:        {"color": "red",    "label": "Modelo ERMAC 2026"},
}

# Pequenos deslocamentos para evitar sobreposição visual entre rotas
ROUTE_OFFSETS: dict[ModelType, tuple[float, float]] = {
    ModelType.STANDARD:        (0.0,      0.0),
    ModelType.HISTORICAL_ONLY: (0.00003,  0.00003),
    ModelType.REAL_TIME_ONLY:  (-0.00003, -0.00003),
    ModelType.PROPOSED:        (-0.00006, 0.00000),
}


# ---------------------------------------------------------------------------
# Funções auxiliares de mapa
# ---------------------------------------------------------------------------


def _base_map(center_lat: float, center_lon: float) -> folium.Map:
    return folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles="CartoDB voyager",
    )


def _add_markers(m: folium.Map) -> None:
    folium.Marker(
        location=list(ORIGIN),
        popup="Origem",
        icon=folium.Icon(color="red", icon="play"),
    ).add_to(m)
    folium.Marker(
        location=list(DESTINATION),
        popup="Destino",
        icon=folium.Icon(color="green", icon="flag"),
    ).add_to(m)


def _add_flood_markers(m: folium.Map, *, show_buffer: bool = False) -> None:
    for lat, lon in CURRENT_FLOODS:
        folium.Marker(
            location=[lat, lon],
            popup="Ponto de Alagamento",
            icon=folium.Icon(color="black", icon="times", prefix="fa"),
        ).add_to(m)
        if show_buffer:
            folium.Circle(
                location=[lat, lon],
                radius=200,
                color="red",
                fill=True,
                fill_color="red",
                fill_opacity=0.2,
            ).add_to(m)


def _add_route(
    m: folium.Map,
    result: RouteResult,
    routing: FloodRouting,
) -> None:
    if result.is_blocked:
        return
    style = ROUTE_STYLES[result.model_type]
    offset = ROUTE_OFFSETS[result.model_type]
    coords = [
        (lat + offset[0], lon + offset[1])
        for lat, lon in routing.get_route_coordinates(result.path)
    ]
    folium.PolyLine(
        coords,
        color=style["color"],
        weight=5,
        opacity=0.9,
        tooltip=style["label"],
    ).add_to(m)


def _print_summary(results: dict[ModelType, RouteResult]) -> None:
    print("\n" + "=" * 60)
    print("RESULTADOS DAS ROTAS")
    print("=" * 60)
    for model_type, result in results.items():
        style = ROUTE_STYLES[model_type]
        color_tag = f"[{style['color'].upper():8s}]"
        print(f"{color_tag} {style['label']:35s}: {result}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Execução principal
# ---------------------------------------------------------------------------


def main() -> None:
    model = FloodRouting(**BBOX, history_shp_path=HISTORY_SHP, Q=CALIBRATION_Q)

    print("Calculando as quatro variantes de rota...")
    results = model.find_all_routes(ORIGIN, DESTINATION, CURRENT_FLOODS, raining=RAINING)

    _print_summary(results)

    center_lat = (ORIGIN[0] + DESTINATION[0]) / 2
    center_lon = (ORIGIN[1] + DESTINATION[1]) / 2

    map_plain = _base_map(center_lat, center_lon)
    map_buffer = _base_map(center_lat, center_lon)
    map_heatmap = _base_map(center_lat, center_lon)

    # Mapa de calor histórico
    heat_data = [
        [lat, lon] for lat, lon in model.get_historical_points_latlon()
    ]
    HeatMap(heat_data, radius=15, blur=10, min_opacity=0.3, max_val=1.0).add_to(
        map_heatmap
    )

    for result in results.values():
        for m in (map_plain, map_buffer, map_heatmap):
            _add_route(m, result, model)

    for m in (map_plain, map_buffer, map_heatmap):
        _add_markers(m)

    _add_flood_markers(map_plain, show_buffer=False)
    _add_flood_markers(map_buffer, show_buffer=True)
    _add_flood_markers(map_heatmap, show_buffer=True)

    output_dir = os.path.dirname(os.path.abspath(__file__))
    map_plain.save(os.path.join(output_dir, "exemplo_mapa.html"))
    map_buffer.save(os.path.join(output_dir, "exemplo_mapa_buffer.html"))
    map_heatmap.save(os.path.join(output_dir, "exemplo_mapa_historico.html"))

    print("Mapas gerados com sucesso:")
    print("  - exemplo_mapa.html")
    print("  - exemplo_mapa_buffer.html")
    print("  - exemplo_mapa_historico.html")


if __name__ == "__main__":
    main()