"""
Orquestrador end-to-end: gera CSVs ERMAC, injeta no Valhalla, reinicia o servico
e roda smoke test.

Use sempre que o shapefile historico for atualizado, ou quando quiser refazer
a injecao do zero. Os tiles sao modificados in-place, entao um backup e feito
em data/tiles_backup/ caso ainda nao exista.

Uso:
    python scripts/refresh_traffic.py
    python scripts/refresh_traffic.py --skip-backup
    python scripts/refresh_traffic.py --no-restart  (para inspecionar CSVs antes)
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

LOG = logging.getLogger("refresh_traffic")
ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    LOG.info("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=True, **kwargs)


def backup_tiles(force: bool) -> None:
    backup = ROOT / "data" / "tiles_backup"
    if backup.exists() and not force:
        LOG.info("backup ja existe em %s -- pulando (use --force-backup pra refazer)", backup)
        return
    if backup.exists() and force:
        LOG.info("removendo backup antigo: %s", backup)
        shutil.rmtree(backup)
    LOG.info("copiando data/tiles -> data/tiles_backup (~1 GB, pode demorar)")
    t0 = time.time()
    shutil.copytree(ROOT / "data" / "tiles", backup)
    LOG.info("backup ok em %.1fs", time.time() - t0)


def build_csvs(python_exe: Path, q: float) -> None:
    run([
        str(python_exe),
        str(ROOT / "scripts" / "build_traffic_csvs.py"),
        "--clean",
        "--q", str(q),
    ])


def inject_traffic(container: str) -> None:
    LOG.info("injetando CSVs nos tiles via %s", container)
    cp = run(
        # ATENCAO: <traffic_dir> e POSICIONAL, nao flag (-t nao existe)
        ["docker", "exec", container, "valhalla_add_predicted_traffic",
         "-c", "/data/valhalla.json", "/data/traffic_csvs"],
        capture_output=True,
        text=True,
    )
    all_lines = (cp.stderr + cp.stdout).strip().splitlines()
    for line in all_lines[-10:]:
        LOG.info("valhalla> %s", line)
    if not any("Updated" in line and "directed edges" in line for line in all_lines):
        raise RuntimeError("nao confirmou 'Updated N directed edges' no log -- veja stderr/stdout acima")


def restart_service(container: str) -> None:
    LOG.info("reiniciando container %s", container)
    run(["docker", "restart", container], capture_output=True)
    LOG.info("aguardando healthy (60s max)...")
    t0 = time.time()
    while time.time() - t0 < 60:
        out = subprocess.run(
            ["docker", "inspect", container, "--format", "{{.State.Health.Status}}"],
            capture_output=True, text=True,
        )
        if out.stdout.strip() == "healthy":
            LOG.info("healthy em %.1fs", time.time() - t0)
            return
        time.sleep(1)
    raise RuntimeError("timeout esperando healthy")


def smoke_test(valhalla_url: str) -> None:
    """Roda 2 requests (modo seco / modo chuva) e mostra a diferenca de tempo."""
    LOG.info("smoke test: rota seco vs chuva no mesmo trecho")

    def route(date_time: str) -> tuple[float, float]:
        body = {
            "locations": [
                {"lat": -23.5695, "lon": -46.6080},
                {"lat": -23.5675, "lon": -46.6078},
            ],
            "costing": "auto",
            "date_time": {"type": 1, "value": date_time},
        }
        r = requests.post(f"{valhalla_url}/route", json=body, timeout=30)
        r.raise_for_status()
        s = r.json()["trip"]["summary"]
        return float(s["length"]), float(s["time"])

    dry_len, dry_t = route("2026-05-18T03:00")  # noite -> free_flow
    wet_len, wet_t = route("2026-05-18T13:00")  # dia   -> constrained
    LOG.info("  seco  (T03:00, free_flow):   length=%.3fkm time=%.1fs", dry_len, dry_t)
    LOG.info("  chuva (T13:00, constrained): length=%.3fkm time=%.1fs", wet_len, wet_t)
    if wet_t <= dry_t + 0.5:
        LOG.warning("ATENCAO: tempo chuva nao maior que seco. Injecao pode nao ter pegado.")
    else:
        diff_pct = (wet_t - dry_t) / dry_t * 100
        LOG.info("  fidelidade ERMAC ok: penalidade efetiva = +%.1f%%", diff_pct)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh pipeline ERMAC -> Valhalla")
    parser.add_argument("--container", default="valhalla")
    parser.add_argument("--valhalla-url", default="http://localhost:8002")
    parser.add_argument("--q", type=float, default=10.0)
    parser.add_argument("--python", default=str(ROOT / "scripts" / ".venv" / "Scripts" / "python.exe"),
                        help="Python da venv com geopandas instalado")
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--force-backup", action="store_true",
                        help="Sobrescreve backup existente")
    parser.add_argument("--no-restart", action="store_true",
                        help="Nao reinicia o container (uteis CSVs ficam visiveis sem efeito)")
    parser.add_argument("--no-smoke", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    python_exe = Path(args.python)
    if not python_exe.exists():
        LOG.error("Python nao encontrado: %s -- rode 'python -m venv scripts/.venv' primeiro", python_exe)
        return 1

    if not args.skip_backup:
        backup_tiles(force=args.force_backup)

    build_csvs(python_exe, args.q)
    inject_traffic(args.container)

    if args.no_restart:
        LOG.info("--no-restart: o servico ainda usa os tiles em memoria. Reinicie manualmente para aplicar.")
        return 0

    restart_service(args.container)

    if not args.no_smoke:
        smoke_test(args.valhalla_url)

    LOG.info("Tudo pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
