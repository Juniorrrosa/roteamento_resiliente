"""
Pipeline ERMAC -> Valhalla: gera CSVs de tráfego que codificam h(e)/Q.

Modelo matemático (paper ERMAC 2026):
    w(e) = b(e) * (1 + h(e)/Q) * l(e)

Mapeamento para o Valhalla:
- l(e)                          length nativo dos tiles
- b(e) = inf (alagado em RT)    exclude_locations no request HTTP
- (1 + h(e)/Q)                  reducao de velocidade encodada no tile
                                speed_efetivo = speed_original / (1 + h/Q)

O switch chuva ON/OFF é feito pelo backend trocando date_time:
- date_time noturno   -> Valhalla usa free_flow_speed   (modo seco)
- date_time diurno    -> Valhalla usa constrained_speed (modo chuva)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import geopandas as gpd
import requests
from requests.adapters import HTTPAdapter
from shapely.geometry import Point
from urllib3.util.retry import Retry

LOG = logging.getLogger("build_traffic_csvs")


@dataclass
class EdgeRecord:
    level: int
    tile_id: int
    edge_id: int
    h: int
    default_speed_kmh: int
    length_m: int
    way_id: int | None
    correlated_lat: float
    correlated_lon: float

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.level, self.tile_id, self.edge_id)

    @property
    def edge_id_str(self) -> str:
        return f"{self.level}/{self.tile_id}/{self.edge_id}"

    def penalized_speed_kmh(self, q: float) -> int:
        if self.h <= 0:
            return self.default_speed_kmh
        return max(1, int(round(self.default_speed_kmh / (1.0 + self.h / q))))


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _http_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),
    )
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def read_historical_points(shp_path: Path, condition_value: str) -> list[tuple[float, float]]:
    LOG.info("Lendo shapefile: %s", shp_path)
    gdf = gpd.read_file(shp_path)
    if "CONDICAO" not in gdf.columns:
        raise ValueError(f"shapefile sem coluna CONDICAO: {shp_path}")
    total = len(gdf)
    gdf = gdf[gdf["CONDICAO"] == condition_value]
    LOG.info("Pontos %s: %d / %d total", condition_value, len(gdf), total)
    gdf = gdf.to_crs(4326)
    pts = [(geom.y, geom.x) for geom in gdf.geometry if isinstance(geom, Point)]
    if len(pts) < len(gdf):
        LOG.warning("Geometrias nao-Point ignoradas: %d", len(gdf) - len(pts))
    return pts


def locate_batch(
    session: requests.Session,
    valhalla_url: str,
    points: list[tuple[float, float]],
    timeout_s: float,
) -> list:
    body = {
        "locations": [{"lat": lat, "lon": lon} for lat, lon in points],
        "costing": "auto",
        "verbose": True,
    }
    r = session.post(f"{valhalla_url}/locate", json=body, timeout=timeout_s)
    r.raise_for_status()
    return r.json()


def collect_edge_hits(
    valhalla_url: str,
    points: list[tuple[float, float]],
    batch_size: int,
    max_snap_distance_m: float,
    request_timeout_s: float,
) -> dict[tuple[int, int, int], EdgeRecord]:
    edges: dict[tuple[int, int, int], EdgeRecord] = {}
    session = _http_session()
    n_batches = (len(points) + batch_size - 1) // batch_size
    skipped_points = 0

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        try:
            results = locate_batch(session, valhalla_url, batch, request_timeout_s)
        except requests.RequestException as exc:
            LOG.error("Batch %d/%d falhou: %s -- pulando", i // batch_size + 1, n_batches, exc)
            skipped_points += len(batch)
            continue

        for loc_result in results:
            if not loc_result.get("edges"):
                skipped_points += 1
                continue
            for edge in loc_result["edges"]:
                if edge.get("distance", 1e9) > max_snap_distance_m:
                    continue
                eid = edge["edge_id"]
                key = (eid["level"], eid["tile_id"], eid["id"])
                rec = edges.get(key)
                if rec is None:
                    speeds = edge["edge"].get("speeds", {})
                    default_speed = speeds.get("default") or 50
                    length = edge["edge"].get("geo_attributes", {}).get("length") or 1
                    rec = EdgeRecord(
                        level=eid["level"],
                        tile_id=eid["tile_id"],
                        edge_id=eid["id"],
                        h=0,
                        default_speed_kmh=int(default_speed),
                        length_m=int(length),
                        way_id=edge.get("edge_info", {}).get("way_id"),
                        correlated_lat=edge.get("correlated_lat", 0.0),
                        correlated_lon=edge.get("correlated_lon", 0.0),
                    )
                    edges[key] = rec
                rec.h += 1
        LOG.info("batch %3d/%3d ok (%d pts)", i // batch_size + 1, n_batches, len(batch))

    if skipped_points:
        LOG.warning("Pontos sem aresta proxima (ate %dm): %d", int(max_snap_distance_m), skipped_points)
    return edges


def tile_relative_path(level: int, tile_id: int) -> Path:
    if level >= 2:
        s = f"{tile_id:09d}"
        return Path(f"{level}/{s[0:3]}/{s[3:6]}/{s[6:9]}.csv")
    s = f"{tile_id:06d}"
    return Path(f"{level}/{s[0:3]}/{s[3:6]}.csv")


def write_traffic_csvs(edges: dict, output_dir: Path, q: float, clean: bool) -> int:
    if clean and output_dir.exists():
        LOG.info("--clean: removendo %s", output_dir)
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    by_tile: dict[tuple[int, int], list[EdgeRecord]] = defaultdict(list)
    for rec in edges.values():
        by_tile[(rec.level, rec.tile_id)].append(rec)

    n_files = 0
    n_rows = 0
    for (level, tile_id), recs in by_tile.items():
        out_path = output_dir / tile_relative_path(level, tile_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as f:
            w = csv.writer(f)
            for rec in recs:
                w.writerow([rec.edge_id_str, rec.default_speed_kmh, rec.penalized_speed_kmh(q)])
                n_rows += 1
        n_files += 1
    LOG.info("CSVs gerados: %d (total %d arestas)", n_files, n_rows)
    return n_files


def write_reports(edges: dict, q: float, output_dir: Path) -> None:
    """Gera relatórios para auditoria: distribuição de h, lista de arestas, sumário JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    h_dist: dict[int, int] = defaultdict(int)
    for rec in edges.values():
        h_dist[rec.h] += 1

    summary = {
        "q": q,
        "total_edges": len(edges),
        "h_distribution": dict(sorted(h_dist.items())),
        "max_h": max((rec.h for rec in edges.values()), default=0),
        "worst_case_speed_ratio": (1.0 / (1.0 + max((rec.h for rec in edges.values()), default=0) / q)),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    rows = [
        {
            **asdict(rec),
            "penalized_speed_kmh": rec.penalized_speed_kmh(q),
            "speed_ratio": round(rec.penalized_speed_kmh(q) / rec.default_speed_kmh, 4) if rec.default_speed_kmh else 0,
        }
        for rec in sorted(edges.values(), key=lambda r: -r.h)
    ]
    if rows:
        with (output_dir / "affected_edges.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    LOG.info("Relatorios salvos em %s", output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline ERMAC -> CSVs de trafego para Valhalla")
    parser.add_argument("--shapefile", default="modelo_py/Alag-Inun_2015-2025.shp",
                        help="Caminho do shapefile historico (relativo ao root do projeto)")
    parser.add_argument("--condition", default="INTRANSITAVEL",
                        help="Valor da coluna CONDICAO a filtrar")
    parser.add_argument("--valhalla-url", default="http://localhost:8002",
                        help="URL do servico Valhalla")
    parser.add_argument("--output", default="data/traffic_csvs",
                        help="Pasta de saida dos CSVs (relativa ao root)")
    parser.add_argument("--report-dir", default="data/traffic_report",
                        help="Pasta de saida dos relatorios (relativa ao root)")
    parser.add_argument("--q", type=float, default=10.0,
                        help="Fator de calibracao Q do paper (sensibilidade ao historico)")
    parser.add_argument("--max-distance", type=float, default=200.0,
                        help="Distancia maxima em metros do ponto ate a aresta para considerar")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Tamanho do batch de pontos por request /locate")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="Timeout em segundos por request /locate")
    parser.add_argument("--clean", action="store_true",
                        help="Limpa a pasta de saida antes de escrever")
    parser.add_argument("--summary-only", action="store_true",
                        help="So roda /locate e gera relatorios; nao escreve CSVs")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _setup_logging(args.verbose)

    project_root = Path(__file__).resolve().parent.parent
    shp = (project_root / args.shapefile).resolve()
    out = (project_root / args.output).resolve()
    report = (project_root / args.report_dir).resolve()

    if not shp.exists():
        LOG.error("shapefile nao encontrado: %s", shp)
        return 1

    start = time.time()
    points = read_historical_points(shp, args.condition)
    if not points:
        LOG.warning("Sem pontos para processar. Saindo.")
        return 0

    LOG.info("Consultando /locate em %s (batches de %d)...", args.valhalla_url, args.batch_size)
    edges = collect_edge_hits(
        args.valhalla_url,
        points,
        batch_size=args.batch_size,
        max_snap_distance_m=args.max_distance,
        request_timeout_s=args.timeout,
    )
    LOG.info("Arestas unicas afetadas: %d", len(edges))

    write_reports(edges, args.q, report)

    if args.summary_only:
        LOG.info("--summary-only: nao gerando CSVs.")
    else:
        write_traffic_csvs(edges, out, args.q, clean=args.clean)

    LOG.info("Pronto em %.1fs", time.time() - start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
