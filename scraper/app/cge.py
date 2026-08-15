"""Coleta e parsing dos alagamentos do CGE-SP.

Camadas:
- `fetch_html_via_selenium`: dispara Selenium (Chromium), digita a data no campo
  `dataBusca`, espera o JS renderizar a tabela, devolve o HTML completo.
- `parse_alagamentos_html`: recebe HTML cru e devolve uma lista de `RawRecord`.

Separamos as duas camadas para permitir testar o parser sem rodar browser.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Tag

LOG = logging.getLogger(__name__)


# --- Normalizacao de enderecos do CGE ------------------------------------------
# O CGE usa formato informal: abreviado, caixa alta, sem numero e com jargao de
# pista/sentido. Isso derruba o geocoder. Aqui limpamos o nome da via.
_PREFIXO_VIA = {
    "AV": "Avenida", "AVN": "Avenida", "AVE": "Avenida",
    "R": "Rua", "RUA": "Rua",
    "PC": "Praça", "PCA": "Praça", "PÇA": "Praça", "PRACA": "Praça",
    "AL": "Alameda", "TV": "Travessa", "TRAV": "Travessa",
    "EST": "Estrada", "ESTR": "Estrada", "ROD": "Rodovia",
    "VD": "Viaduto", "VIAD": "Viaduto", "PTE": "Ponte", "LGO": "Largo",
    "MARG": "Marginal",
}
_HONORIFICO = {
    "DR": "Doutor", "DRA": "Doutora", "PROF": "Professor", "PROFA": "Professora",
    "PRES": "Presidente", "MAL": "Marechal", "GAL": "General", "CEL": "Coronel",
    "ENG": "Engenheiro", "VER": "Vereador", "SEN": "Senador", "MJ": "Major",
    "CMTE": "Comandante", "STO": "Santo", "STA": "Santa",
}
# jargao de pista/sentido do CGE que atrapalha o geocoder
_JARGAO = {"CBAS", "EXPRESSA", "EXPRESSO", "PISTA", "LOCAL", "CENTRAL", "COMPLEXO"}
# correcoes pontuais comuns no CGE (grafia/acentos)
_CORRECAO = {"TIETE": "Tietê", "BRAZIL": "Brasil"}
_CONECTORES = {"de", "da", "do", "das", "dos", "e"}


def normalize_cge_local(local: str) -> str:
    """Limpa o nome da via do CGE para melhorar o geocoding.

    Ex.: "AV MORVAN DIAS DE FIGUEIREDO" -> "Avenida Morvan Dias de Figueiredo"
         "MARGINAL TIETE CBAS EXPRESSA" -> "Marginal Tietê"
         "AV VITAL BRAZIL"              -> "Avenida Vital Brasil"
    """
    raw = re.sub(r"[.,;/]", " ", local or "")
    tokens = [t for t in raw.split() if t]
    out: list[str] = []
    for i, tok in enumerate(tokens):
        up = tok.upper()
        if up in _JARGAO:
            continue
        if i == 0 and up in _PREFIXO_VIA:
            out.append(_PREFIXO_VIA[up])
        elif up in _HONORIFICO:
            out.append(_HONORIFICO[up])
        elif up in _CORRECAO:
            out.append(_CORRECAO[up])
        else:
            low = tok.lower()
            out.append(low if low in _CONECTORES else low.capitalize())
    if out and out[0].lower() in _CONECTORES:
        out[0] = out[0].capitalize()
    return " ".join(out).strip()


@dataclass
class RawRecord:
    """Registro cru de um alagamento, antes do geocoding."""
    data_ocorrencia: str    # dd/mm/YYYY
    bairro: str
    horario: str            # HH:MM:SS
    local: str              # nome da rua/avenida
    sentido: str            # direcao do alagamento (string livre)
    referencia: str         # ponto de referencia textual (string livre)

    @property
    def local_norm(self) -> str:
        """Nome da via normalizado (usado na busca estruturada do Nominatim)."""
        return normalize_cge_local(self.local)

    def endereco_para_geocode(self, cidade: str = "São Paulo, SP, Brasil") -> str:
        """Monta um endereco textual (normalizado) para exibicao/registro."""
        parts = [self.local_norm, self.bairro, cidade]
        return ", ".join(p for p in parts if p)


# ============================================================================
# Parser (sem Selenium)
# ============================================================================

def _strip(s: str | None) -> str:
    return (s or "").strip()


def _split_lines(s: str) -> list[str]:
    return [line.strip() for line in s.splitlines() if line.strip()]


def parse_alagamentos_html(html: str, data_ocorrencia: str) -> list[RawRecord]:
    """Parseia o HTML da pagina de alagamentos e devolve os registros.

    A pagina apresenta zonas (`table.tb-pontos-de-alagamentos`); cada zona tem
    um cabecalho com o nome do bairro e uma ou mais linhas com horario+local
    a esquerda e sentido+referencia a direita.
    """
    soup = BeautifulSoup(html, "lxml")
    tabelas = soup.select("table.tb-pontos-de-alagamentos")
    LOG.debug("encontradas %d tabelas .tb-pontos-de-alagamentos", len(tabelas))

    registros: list[RawRecord] = []
    for tabela in tabelas:
        # Bairro vem no cabecalho da tabela (classes do original).
        bairro_node = tabela.select_one(
            ".bairro.arial-bairros-alag, .bairro, .arial-bairros-alag"
        )
        bairro = _strip(bairro_node.get_text(" ", strip=True)) if bairro_node else ""

        # Cada linha de alagamento tem uma celula "col-local" e uma celula com Sentido.
        locais = tabela.select(".arial-descr-alag.col-local")
        # Todas as celulas com classe arial-descr-alag (inclui col-local e direita).
        todas_descr = tabela.select(".arial-descr-alag")
        sentidos_refs = [c for c in todas_descr if "Sentido:" in c.get_text()]

        if len(locais) != len(sentidos_refs):
            LOG.warning(
                "bairro=%r: contagem desigual locais=%d sentidos=%d (zipando ate o menor)",
                bairro, len(locais), len(sentidos_refs),
            )
        for local_cell, sentido_cell in zip(locais, sentidos_refs):
            local_lines = _split_lines(local_cell.get_text("\n"))
            sent_lines = _split_lines(sentido_cell.get_text("\n"))

            horario = local_lines[0] if local_lines else ""
            local = local_lines[1] if len(local_lines) > 1 else ""

            sentido = ""
            referencia = ""
            for line in sent_lines:
                if line.lower().startswith("sentido:"):
                    sentido = line.split(":", 1)[1].strip()
                elif line.lower().startswith("refer") and ":" in line:
                    referencia = line.split(":", 1)[1].strip()

            registros.append(
                RawRecord(
                    data_ocorrencia=data_ocorrencia,
                    bairro=bairro,
                    horario=horario,
                    local=local,
                    sentido=sentido,
                    referencia=referencia,
                )
            )

    LOG.info("parser: %d registros extraidos para %s", len(registros), data_ocorrencia)
    return registros


# ============================================================================
# Selenium (com browser real)
# ============================================================================

def fetch_html_via_selenium(
    target_date: date,
    cge_url: str,
    page_load_timeout: int,
    element_wait_timeout: int,
    headless: bool,
) -> str:
    """Abre a pagina do CGE, submete a data, devolve o HTML renderizado."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    LOG.info("fetch: data=%s headless=%s url=%s", target_date.isoformat(), headless, cge_url)

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,1024")

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(page_load_timeout)
    try:
        driver.get(cge_url)
        wait = WebDriverWait(driver, element_wait_timeout)

        # Submete a data no formato dd/mm/YYYY (igual ao scraper original).
        date_str = target_date.strftime("%d/%m/%Y")
        campo = wait.until(EC.presence_of_element_located((By.NAME, "dataBusca")))
        campo.send_keys(Keys.CONTROL, "a")
        campo.send_keys(Keys.BACKSPACE)
        campo.send_keys(date_str)
        campo.send_keys(Keys.RETURN)

        # Aguarda a renderizacao. A pagina pode legitimamente ficar sem tabelas
        # (dia sem alagamentos) — esperamos um sinal qualquer e devolvemos o HTML.
        time.sleep(2.0)  # JS demora um pouco apos o submit
        html = driver.page_source
        LOG.info("fetch ok: %d bytes", len(html))
        return html
    finally:
        driver.quit()
