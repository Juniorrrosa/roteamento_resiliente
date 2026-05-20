# Scraper — Roteamento Resiliente

Coleta alagamentos ativos do CGE-SP (<https://www.cgesp.org/v3/alagamentos.jsp>), geocodifica via Nominatim local e empurra o snapshot para o backend FastAPI.

Reimplementação do scraper original de <https://github.com/vitor-yuichi/cge_scrapper>, adaptado para:

- Geocoding via Nominatim (não mais Google Maps API)
- Persistência via API do backend (`POST /alagamentos/snapshot`), não Excel
- Modo "agora" (data corrente) como padrão; o modo histórico continua disponível via `--date`
- Container Docker isolado com Chromium + chromedriver
- Parser HTML separado da camada Selenium para facilitar testes

## Comandos

```
cge-scraper run [--once] [--dry-run] [--date DD/MM/YYYY]
cge-scraper parse <html_path>            # parsing offline (debug/teste)
```

### Modos

| Modo | Comando | Descrição |
|---|---|---|
| **Padrão (hoje, push)** | `cge-scraper run` | Coleta hoje, geocoda, faz POST `/alagamentos/snapshot` |
| **Dry-run** | `cge-scraper run --dry-run` | Coleta + geocoda, mas NÃO faz push (só imprime). Útil para testar antes de tocar o DB |
| **Data específica** | `cge-scraper run --date 18/05/2026` | Coleta a data informada |
| **Parser offline** | `cge-scraper parse fixture.html` | Lê HTML local, devolve registros parseados. Não requer Chrome nem rede |

## Rodar local

```powershell
cd scraper
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env       # ajuste se preciso

# Pre-requisito: ter Chromium ou Chrome instalado
.\.venv\Scripts\python.exe -m app.cli run --once --dry-run
```

## Rodar via Docker (recomendado em produção)

O container do scraper está no `runtime/docker-compose.yml` atrás do profile `scraper` — não sobe junto com a stack. Rodada típica:

```powershell
cd runtime
docker compose --profile scraper run --rm scraper run --once
```

A imagem inclui Chromium + chromedriver. Tudo cabe num único container, sem necessidade de Selenium Grid.

## Configuração (env vars)

| Var | Default | Descrição |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | URL do backend (em compose: `http://backend:8000`) |
| `CGE_URL` | `https://www.cgesp.org/v3/alagamentos.jsp` | Página do CGE. Não mudar a não ser que o CGE migre |
| `PAGE_LOAD_TIMEOUT` | 30 | Timeout em segundos do `driver.get()` |
| `ELEMENT_WAIT_TIMEOUT` | 15 | Espera por elementos da tabela aparecerem após submit |
| `HTTP_TIMEOUT` | 30 | Timeout das chamadas ao backend |
| `LOG_LEVEL` | `INFO` | `DEBUG` para inspecionar selectors |
| `HEADLESS` | `true` | Em `false`, abre o browser visualmente (debug local) |

## Estrutura

```
scraper/
├── pyproject.toml          deps + CLI entry point
├── Dockerfile              python:3.12-slim + chromium + chromedriver
├── .env.example
├── app/
│   ├── config.py           pydantic-settings
│   ├── cge.py              Selenium fetcher + HTML parser (BS4)
│   ├── geocoder.py         cliente HTTP do /geocode do backend (Nominatim com cache)
│   ├── backend.py          cliente HTTP do /alagamentos/snapshot
│   ├── pipeline.py         orquestrador: fetch -> parse -> geocode -> push
│   └── cli.py              argparse entrypoint
└── tests/
    ├── fixtures/
    │   └── cge_sample.html
    └── test_cge_parser.py
```

## Modo polling (fase 3)

Hoje o scraper roda em batch (sob demanda). Em uma próxima fase, podemos:

- Wrapper em `--loop --interval 5min` rodando como worker container no compose
- Cadência adaptativa (ver `docs/09-roadmap.md`)
- Sinal de saúde / alerta se falhar por >15 min

Por ora, dispare manualmente quando quiser atualizar o snapshot.
