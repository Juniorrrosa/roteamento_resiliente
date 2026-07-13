"""Entrypoint CLI do scraper."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from app.cge import parse_alagamentos_html
from app.config import settings
from app.pipeline import raw_records_to_dicts, run_pipeline


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_date_arg(s: str) -> date:
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"data invalida (esperado dd/mm/YYYY): {s}") from exc


def cmd_run(args: argparse.Namespace) -> int:
    if args.loop:
        from app.loop import run_loop
        asyncio.run(run_loop())
        return 0
    result = asyncio.run(
        run_pipeline(target_date=args.date, dry_run=args.dry_run, save_html_to=args.save_html)
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    html = Path(args.html).read_text(encoding="utf-8")
    data_str = (args.date or date.today()).strftime("%d/%m/%Y") if args.date else date.today().strftime("%d/%m/%Y")
    records = parse_alagamentos_html(html, data_ocorrencia=data_str)
    print(json.dumps(raw_records_to_dicts(records), indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cge-scraper", description="Scraper do CGE-SP")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Coleta, geocoda e envia ao backend")
    p_run.add_argument("--loop", action="store_true",
                       help="roda em loop continuo com cadencia adaptativa (worker real-time)")
    p_run.add_argument("--once", action="store_true",
                       help="passada unica (padrao quando --loop nao e informado)")
    p_run.add_argument("--date", type=_parse_date_arg, default=None,
                       help="data alvo (dd/mm/YYYY). default: hoje")
    p_run.add_argument("--dry-run", action="store_true",
                       help="nao chama POST /alagamentos/snapshot, so imprime o preview")
    p_run.add_argument("--save-html", default=None, metavar="PATH",
                       help="salva o HTML cru retornado pelo Selenium nesse caminho (debug)")
    p_run.set_defaults(func=cmd_run)

    p_parse = sub.add_parser("parse", help="Parser offline: le HTML local e imprime os registros")
    p_parse.add_argument("html", help="caminho do HTML salvo")
    p_parse.add_argument("--date", type=_parse_date_arg, default=None,
                         help="data a marcar nos registros (default: hoje)")
    p_parse.set_defaults(func=cmd_parse)

    return parser


def main(argv: list[str] | None = None) -> int:
    _setup_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
