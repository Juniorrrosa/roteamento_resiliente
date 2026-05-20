"""Testes do parser HTML do CGE — nao requer Selenium nem rede."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cge import RawRecord, parse_alagamentos_html

FIXTURE = Path(__file__).parent / "fixtures" / "cge_sample.html"
DATA = "20/05/2026"


@pytest.fixture(scope="module")
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parser_total_records(html: str) -> None:
    records = parse_alagamentos_html(html, data_ocorrencia=DATA)
    assert len(records) == 3  # 2 Ipiranga + 1 Bela Vista + 0 Centro


def test_parser_bairros(html: str) -> None:
    records = parse_alagamentos_html(html, data_ocorrencia=DATA)
    bairros = {r.bairro for r in records}
    assert bairros == {"Ipiranga", "Bela Vista"}


def test_parser_extracts_all_fields(html: str) -> None:
    records = parse_alagamentos_html(html, data_ocorrencia=DATA)
    primeiro = next(r for r in records if r.bairro == "Ipiranga" and r.horario == "15:32:10")
    assert primeiro.local == "Avenida do Estado, 6961"
    assert primeiro.sentido == "Bairro/Centro"
    assert primeiro.referencia == "proximo ao viaduto X"
    assert primeiro.data_ocorrencia == DATA


def test_parser_referencia_acento(html: str) -> None:
    """O original tira o prefixo 'Referência:' (com acento). Garantir que nosso parser tambem."""
    records = parse_alagamentos_html(html, data_ocorrencia=DATA)
    for r in records:
        assert not r.referencia.lower().startswith("refer")


def test_parser_sentido_sem_prefixo(html: str) -> None:
    records = parse_alagamentos_html(html, data_ocorrencia=DATA)
    for r in records:
        assert not r.sentido.lower().startswith("sentido")


def test_parser_html_vazio() -> None:
    """Sem tabelas -> lista vazia, sem erro."""
    records = parse_alagamentos_html("<html><body><p>sem alagamentos</p></body></html>", DATA)
    assert records == []


def test_endereco_para_geocode() -> None:
    r = RawRecord(
        data_ocorrencia=DATA,
        bairro="Ipiranga",
        horario="15:00:00",
        local="Avenida do Estado, 6961",
        sentido="Bairro/Centro",
        referencia="ref",
    )
    assert r.endereco_para_geocode() == "Avenida do Estado, 6961, Ipiranga, São Paulo, SP, Brasil"


def test_endereco_para_geocode_sem_bairro() -> None:
    r = RawRecord(
        data_ocorrencia=DATA,
        bairro="",
        horario="00:00:00",
        local="Av X",
        sentido="",
        referencia="",
    )
    # bairro vazio -> nao polui o endereco
    assert r.endereco_para_geocode() == "Av X, São Paulo, SP, Brasil"
