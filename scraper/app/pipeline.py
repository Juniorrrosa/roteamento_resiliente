"""Orquestrador: scrape -> parse -> geocode -> push snapshot."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date

from app.backend import BackendClient, BackendError
from app.cge import RawRecord, fetch_html_via_selenium, parse_alagamentos_html
from app.config import settings
from app.geocoder import BackendGeocoder, GeocodeError

LOG = logging.getLogger(__name__)


async def run_pipeline(
    target_date: date | None = None,
    dry_run: bool = False,
    html_override: str | None = None,
    save_html_to: str | None = None,
) -> dict:
    """Executa o fluxo completo.

    Args:
        target_date: data a coletar (default = hoje).
        dry_run: se True, geocoda mas nao chama o backend.
        html_override: se fornecido, pula o Selenium e usa esse HTML (uso de teste).

    Returns:
        Dict com estatisticas: {total_parsed, geocoded, geocode_fail, pushed, ...}
    """
    target_date = target_date or date.today()
    data_str = target_date.strftime("%d/%m/%Y")

    # 1. Fetch HTML
    if html_override is not None:
        html = html_override
        LOG.info("usando HTML override (%d bytes), pulando Selenium", len(html))
    else:
        html = fetch_html_via_selenium(
            target_date=target_date,
            cge_url=settings.cge_url,
            page_load_timeout=settings.page_load_timeout,
            element_wait_timeout=settings.element_wait_timeout,
            headless=settings.headless,
        )

    if save_html_to:
        from pathlib import Path
        Path(save_html_to).write_text(html, encoding="utf-8")
        LOG.info("HTML salvo em %s", save_html_to)

    # 2. Parse
    raw_records: list[RawRecord] = parse_alagamentos_html(html, data_ocorrencia=data_str)
    LOG.info("parsed: %d alagamentos para %s", len(raw_records), data_str)

    if not raw_records:
        LOG.warning("nenhum alagamento parseado — abortando para nao limpar o DB")
        return {
            "total_parsed": 0,
            "geocoded": 0,
            "geocode_fail": 0,
            "pushed": False,
            "skipped_empty": True,
        }

    # 3. Geocode (via backend, que cacheia no PostGIS)
    geocoder = BackendGeocoder(settings.backend_url, timeout=settings.http_timeout)
    pontos_geocoded: list[dict] = []
    falhas = 0
    try:
        for rec in raw_records:
            endereco = rec.endereco_para_geocode()  # normalizado, para registro/exibicao
            try:
                # busca estruturada: nome da via (normalizado) + bairro
                lat, lng = await geocoder.geocode(rec.local_norm, bairro=rec.bairro)
            except GeocodeError as exc:
                LOG.warning("geocode falhou para %r: %s", endereco, exc)
                falhas += 1
                continue
            pontos_geocoded.append({
                "endereco_raw": endereco,
                "bairro": rec.bairro,
                "referencia": rec.referencia,
                "sentido": rec.sentido,
                "lat": lat,
                "lng": lng,
            })
    finally:
        await geocoder.aclose()

    LOG.info("geocoded: %d ok, %d falhas", len(pontos_geocoded), falhas)

    if not pontos_geocoded:
        LOG.warning("nenhum ponto geocodificado — abortando push")
        return {
            "total_parsed": len(raw_records),
            "geocoded": 0,
            "geocode_fail": falhas,
            "pushed": False,
            "skipped_empty": True,
        }

    # 4. Push snapshot (ou dry-run)
    if dry_run:
        LOG.info("dry-run: NAO faz push. Pontos que seriam enviados:")
        for p in pontos_geocoded:
            LOG.info("  %s", p)
        return {
            "total_parsed": len(raw_records),
            "geocoded": len(pontos_geocoded),
            "geocode_fail": falhas,
            "pushed": False,
            "dry_run": True,
            "preview": pontos_geocoded,
        }

    backend = BackendClient(settings.backend_url, timeout=settings.http_timeout)
    try:
        resp = await backend.push_snapshot(pontos_geocoded)
    except BackendError as exc:
        LOG.error("push falhou: %s", exc)
        raise
    finally:
        await backend.aclose()

    LOG.info("snapshot publicado: %s", resp)
    return {
        "total_parsed": len(raw_records),
        "geocoded": len(pontos_geocoded),
        "geocode_fail": falhas,
        "pushed": True,
        "backend_response": resp,
    }


def raw_records_to_dicts(records: list[RawRecord]) -> list[dict]:
    """Util para CLI parse: devolve em formato JSON-friendly."""
    return [asdict(r) for r in records]
