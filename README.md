# Roteamento Resiliente

Sistema de roteamento urbano para São Paulo que **evita pontos de alagamento em tempo real** e **pondera por histórico de alagamento**, conforme o modelo matemático do paper **ERMAC 2026 — "Resilient routing during flood"** (UNIFESP/Cemaden).

- 🟥 **Restrição dura** — vias alagadas *agora* (fonte CGE-SP) são bloqueadas na rota.
- 🟨 **Restrição suave** — vias com histórico de alagamento têm a velocidade penalizada por `(1 + h(e)/Q)`, então o roteador as evita quando há alternativa razoável.

> 📖 **Documentação completa em [`docs/`](docs/README.md)** — visão geral, arquitetura, modelo matemático, infraestrutura, pipeline, API, quirks, deploy e roadmap.

---

## Pré-requisitos

| Requisito | Para quê | Observação |
|---|---|---|
| **Docker Desktop** (rodando) | Toda a stack (web, API, motor de rota, banco, geocoder) | Único requisito obrigatório |
| **~6 GB de disco livre** | OSM + tiles + Nominatim | O extrato do Sudeste sozinho tem ~850 MB |
| Python 3.11+ *(opcional)* | Pipeline de pesos históricos rodando no host | No Windows com **Smart App Control** o pipeline roda via Docker — ver [passo 3](#3-opcional-pesos-históricos-de-alagamento) |

Não é preciso instalar Node, PostgreSQL, Valhalla nem GDAL na máquina — tudo roda em contêiner.

---

## Instalação e execução

Do zero até a interface web no ar. Comandos em **PowerShell** (Windows); no Linux/macOS troque as crases `` ` `` de continuação de linha por `\`.

### 0. Obter os dados do OSM (uma vez)

O Valhalla precisa de um arquivo OpenStreetMap (`.pbf`). O Geofabrik só fatia o Brasil em macrorregiões, então baixamos o **Sudeste** e recortamos a **região metropolitana de SP** com o `osmium`. Cria a pasta `data/` na raiz do projeto:

```powershell
mkdir data
cd data

# baixa o Sudeste (~850 MB)
curl -L -o sudeste-latest.osm.pbf https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf

# recorta a RMSP -> sao-paulo.osm.pbf (~145 MB). Ajuste a bbox p/ outra area se quiser.
docker run --rm -v "${PWD}:/data" stefda/osmium-tool `
  osmium extract -b -47.05,-24.05,-46.15,-23.25 --strategy smart `
  /data/sudeste-latest.osm.pbf -o /data/sao-paulo.osm.pbf

cd ..
```

> A pasta `data/` **não é commitada** (é pesada e regenerável). A bbox `-47.05,-24.05,-46.15,-23.25` cobre a capital + conurbação (Guarulhos, Osasco, ABC, etc.).

### 1. Gerar os tiles do Valhalla (uma vez)

Transforma o `.pbf` no grafo de roteamento. Rodado **uma única vez** por `.pbf`:

```powershell
docker compose -f build/docker-compose.build.yml up --abort-on-container-exit
```

Leva ~2–3 min. Cria automaticamente `data/tiles/`, `data/valhalla.json` (grafo da RMSP ≈ 565k nós). Avisos sobre `admin.sqlite`/`tz_world.sqlite` são esperados e inofensivos.

### 2. Subir a stack

```powershell
cd runtime
Copy-Item .env.example .env      # edite as senhas se for ambiente compartilhado
docker compose up -d --build
cd ..
```

Isso sobe a stack completa: **Valhalla + PostGIS + Backend (FastAPI) + Frontend (React/nginx) + Nominatim (geocoder) + scraper-worker (coleta em tempo real)**.

> ⏳ **Primeira subida:** o **Nominatim** faz um import inicial de ~3 min (o container fica `health: starting` nesse período) — normal, não reinicie. O `scraper-worker` fica `healthy` após o primeiro ciclo. Se quiser subir só o essencial e rápido: `docker compose up -d valhalla postgis backend frontend`.

✅ **Pronto — interface web em [http://localhost:3000](http://localhost:3000).**

| Serviço | URL | Papel |
|---|---|---|
| 🌐 Interface web | http://localhost:3000 | mapa + busca + rotas |
| API backend | http://localhost:8000 (`/health`, `/rota`, `/alagamentos`, `/geocode`) | orquestra o modelo ERMAC |
| Motor de rotas (Valhalla) | http://localhost:8002 (`/route`, `/status`) | grafo da RMSP |
| Geocoder (Nominatim) | http://localhost:8080 | busca por endereço |

> O `/health` fica `degraded` até o Nominatim terminar o import; depois vai a `ok`. As rotas por clique no mapa já funcionam de imediato; a **penalização por histórico** só aparece após o passo 3.

### 3. (Opcional) Pesos históricos de alagamento

Injeta o `(1 + h(e)/Q)` do modelo ERMAC nos tiles, a partir do shapefile histórico em [`modelo_py/`](modelo_py/). Depois deste passo, o mesmo trecho passa a levar mais tempo no "modo chuva".

> ⚠️ **Windows com Smart App Control (SAC) / WDAC:** a política de segurança do Windows bloqueia as DLLs nativas do GDAL (`pyogrio`), então `python scripts/refresh_traffic.py` **falha no host**. Use o **caminho via Docker** abaixo — ele roda a leitura do shapefile num contêiner Linux, onde a política não se aplica. (Detalhes: [docs/07 — Quirk #8](docs/07-quirks-e-decisoes.md).)

**Caminho A — via Docker (recomendado no Windows):**

```powershell
# 1. gera os CSVs de pesos dentro de um contêiner (na rede do Valhalla)
docker run --rm --network roteamento-resiliente_roteamento -v "${PWD}:/work" -w /work python:3.12-slim `
  sh -c "pip install -q geopandas pyogrio requests && python scripts/build_traffic_csvs.py --clean --q 10.0 --valhalla-url http://valhalla:8002"

# 2. injeta os pesos nos tiles e reinicia o Valhalla
docker exec valhalla valhalla_add_predicted_traffic -c /data/valhalla.json /data/traffic_csvs
docker restart valhalla
```

**Caminho B — via Python no host (Linux/macOS, ou Windows sem SAC):**

```powershell
python -m venv scripts\.venv
.\scripts\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py
```

Validação esperada: **922 pontos** INTRANSITÁVEL → **880 arestas** penalizadas; smoke test mostra o mesmo trecho em **~26 s (seco)** vs **~53 s (chuva)** (+102%). Ver [docs/05 — Pipeline](docs/05-pipeline-trafego.md).

### 4. Coleta de alagamentos em tempo real

O **`scraper-worker` já sobe no passo 2** e coleta o CGE-SP automaticamente, em cadência adaptativa (2–15 min conforme a situação). Nada a fazer aqui — é só acompanhar:

```powershell
cd runtime
docker compose logs -f scraper-worker    # ver os ciclos de coleta
docker compose ps scraper-worker         # healthy = coletando normalmente
```

Para uma **coleta pontual** sob demanda (fora do worker), o modo batch continua disponível:

```powershell
docker compose --profile scraper run --rm scraper run --once
```

> Detalhes da cadência, backoff e variáveis de ambiente em [`scraper/README.md`](scraper/README.md) e [docs/09 — Roadmap, Etapa 6](docs/09-roadmap.md).

---

## Comandos do dia a dia

```powershell
cd runtime
docker compose stop            # pausar (mantém tudo)
docker compose up -d           # subir de novo (tiles e pesos já persistidos)
docker compose ps              # status + healthcheck
docker compose logs -f backend # logs
docker compose down            # remover containers (mantém volumes)
docker compose down -v         # zerar tudo, inclusive dados do PostGIS
```

> **Reinício da máquina / Docker:** os containers têm `restart: unless-stopped` e voltam sozinhos assim que o Docker Desktop abrir. Tiles, pesos e o import do Nominatim ficam persistidos — não precisa refazer nada.

---

## Testar o motor de rota direto

```powershell
curl -X POST http://localhost:8002/route -H "Content-Type: application/json" `
  -d '{\"locations\":[{\"lat\":-23.5695,\"lon\":-46.6080},{\"lat\":-23.5505,\"lon\":-46.6333}],\"costing\":\"auto\",\"date_time\":{\"type\":1,\"value\":\"2026-05-18T13:00\"}}'
```

> **Convenção dos exemplos:** `date_time` **noturno** (~03:00) = modo seco (sem penalidade); **diurno** (~13:00) = modo chuva (com penalidade). O porquê está em [docs/07 — Quirk #1](docs/07-quirks-e-decisoes.md). Mais exemplos em [docs/06 — API](docs/06-api-valhalla.md).

---

## Estrutura do projeto

| Pasta | Conteúdo |
|---|---|
| `docs/` | Documentação operacional e técnica — **comece por aqui** |
| `build/` | `docker-compose.build.yml` — gera os tiles do Valhalla a partir do `.pbf` (rodado uma vez) |
| `runtime/` | `docker-compose.yml` — a infra rodando (Valhalla + PostGIS + Backend + Frontend + Nominatim + Scraper) |
| `data/` | `.pbf` OSM, tiles do Valhalla, CSVs de tráfego, relatórios. **Não commitado.** |
| `modelo_py/` | Protótipo Python do paper + shapefile histórico de alagamentos (entrada do pipeline) |
| `scripts/` | Pipeline ERMAC → Valhalla (`build_traffic_csvs.py`, `refresh_traffic.py`, `seed_demo_alagamentos.py`) |
| `backend/` | Backend FastAPI (`/rota`, `/alagamentos`, `/geocode`, `/health`) |
| `scraper/` | Scraper CGE-SP (Selenium + Nominatim + push snapshot) |
| `frontend/` | Frontend React + Vite + Leaflet (nginx, proxy `/api`) |

Cada componente tem seu próprio README: [`backend/`](backend/README.md), [`frontend/`](frontend/README.md), [`scraper/`](scraper/README.md).

---

## Trocar a área de cobertura

Ajuste a bbox no passo 0, regenere o `.pbf` e rode o build (passo 1) novamente apontando pro arquivo no `build/docker-compose.build.yml`. Após o rebuild, **reinjete os pesos** (passo 3 — no Caminho B, com `--force-backup`), pois o rebuild descarta os pesos anteriores.

## Referências

- Paper: `modelo_py/ERMAC_2026_Gislaine_novomodelo.pdf` *(não versionado)*
- Tiles OSM: <https://download.geofabrik.de/south-america/brazil.html>
- Scraper CGE-SP original: <https://github.com/vitor-yuichi/cge_scrapper>

## Licença

MIT — ver [LICENSE](LICENSE).
