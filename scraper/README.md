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
| **Loop (real-time)** | `cge-scraper run --loop` | Worker autônomo: coleta em **cadência adaptativa** até ser parado. É como o `scraper-worker` roda no compose |
| **Passada única (push)** | `cge-scraper run` (ou `run --once`) | Coleta hoje, geocoda, faz POST `/alagamentos/snapshot` e sai |
| **Dry-run** | `cge-scraper run --dry-run` | Coleta + geocoda, mas NÃO faz push (só imprime). Útil para testar antes de tocar o DB |
| **Data específica** | `cge-scraper run --date 18/05/2026` | Coleta a data informada |
| **Parser offline** | `cge-scraper parse fixture.html` | Lê HTML local, devolve registros parseados. Não requer Chrome nem rede |

### Cadência do modo loop

O `--loop` ajusta o intervalo entre coletas conforme a situação (lógica em `app/loop.py`):

| Situação | Intervalo | Env |
|---|---|---|
| Achou ≥ 1 alagamento no último ciclo | **2 min** | `POLL_INTERVAL_ACTIVE` |
| 0 alagamentos, < 1h desde o último | **5 min** | `POLL_INTERVAL_NORMAL` |
| 0 alagamentos e ≥ 1h sem nenhum | **15 min** | `POLL_INTERVAL_QUIET` (`QUIET_AFTER_SECONDS`) |
| Erro de scraping/push | **backoff** 30s → 5 min | `BACKOFF_BASE_SECONDS` / `BACKOFF_CAP_SECONDS` |

Falha contínua por > 15 min (`ALERT_AFTER_SECONDS`) emite log **CRITICAL**. A cada ciclo bem-sucedido o loop grava `HEARTBEAT_PATH` (`/tmp/scraper_heartbeat`), lido pelo healthcheck do container.

## Rodar local

```powershell
cd scraper
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env       # ajuste se preciso

# Pre-requisito: ter Chromium ou Chrome instalado
.\.venv\Scripts\python.exe -m app.cli run --once --dry-run
```

## Rodar via Docker (recomendado)

Há **dois** serviços no `runtime/docker-compose.yml`, ambos usando a mesma imagem:

- **`scraper-worker`** — modo loop (real-time). **Sobe junto com a stack** (`docker compose up -d`) e se mantém rodando (`restart: unless-stopped`). É o que você quer no dia a dia.
- **`scraper`** — modo batch, atrás do profile `scraper`. Para uma coleta pontual sob demanda:

```powershell
cd runtime
docker compose --profile scraper run --rm scraper run --once
```

Acompanhar o worker:

```powershell
docker compose logs -f scraper-worker
docker compose ps scraper-worker      # healthy = heartbeat recente
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
| `POLL_INTERVAL_NORMAL` | 300 | Loop: intervalo em condição normal (s) |
| `POLL_INTERVAL_ACTIVE` | 120 | Loop: intervalo quando há alagamento ativo (s) |
| `POLL_INTERVAL_QUIET` | 900 | Loop: intervalo após `QUIET_AFTER_SECONDS` sem nada (s) |
| `QUIET_AFTER_SECONDS` | 3600 | Loop: tempo sem alagamentos para cair na cadência lenta (s) |
| `BACKOFF_BASE_SECONDS` | 30 | Loop: base do backoff exponencial em erro (s) |
| `BACKOFF_CAP_SECONDS` | 300 | Loop: teto do backoff (s) |
| `ALERT_AFTER_SECONDS` | 900 | Loop: log CRITICAL se falhando há mais que isso (s) |
| `HEARTBEAT_PATH` | `/tmp/scraper_heartbeat` | Loop: arquivo de heartbeat lido pelo healthcheck |

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
│   ├── loop.py             modo real-time: cadência adaptativa + backoff + heartbeat
│   └── cli.py              argparse entrypoint
└── tests/
    ├── fixtures/
    │   └── cge_sample.html
    ├── test_cge_parser.py
    └── test_loop.py        cadência/backoff (funções puras) + run_loop injetado
```

## Rodar os testes

```powershell
# dentro de um container (evita depender do Python/So do host)
cd scraper
docker run --rm -v "${PWD}:/src" -w /src python:3.12-slim sh -c "pip install -q -e '.[dev]' && pytest -q"
```

Os testes de cadência não tocam rede nem Selenium — `run_loop` recebe `pipeline_fn`, `sleep_fn` e clocks injetáveis.
