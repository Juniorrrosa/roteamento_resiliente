# 02 — Arquitetura

## Diagrama de alto nível

```
                      ┌─────────────────┐
                      │ Frontend (TODO) │
                      │ React + Leaflet │
                      └────────┬────────┘
                               │ HTTP REST
                               ▼
                      ┌─────────────────┐
                      │ Backend ✓       │
                      │ FastAPI         │
                      │  /rota          │
                      │  /alagamentos   │
                      │  /geocode       │
                      │  /health        │
                      └─┬─────────┬──┬──┘
                        │         │  │
        ┌───────────────┘         │  └─────────────┐
        ▼                         ▼                ▼
  ┌──────────┐            ┌──────────┐      ┌──────────────┐
  │ Valhalla │            │ PostGIS  │      │  Nominatim   │
  │  :8002   │            │  :5432   │      │   :8080      │
  │ (route + │            │ (DB:     │      │ (geocoding)  │
  │  locate) │            │  RT +    │      │              │
  │          │            │  cache)  │      │              │
  └──────────┘            └──────────┘      └──────────────┘
        │                                          │
        │  tiles RMSP                              │  data: PBF
        │  (128 MB)                                │  (137 MB)
        │  + speeds                                │  importacao:
        │  injetadas                               │  ~3-5 GB
        ▼                                          ▼
        ────────── volume: ./data/ ──────────
        ├── sao-paulo.osm.pbf      (.pbf OSM bruto, recorte RMSP, lido por Valhalla e Nominatim)
        ├── valhalla.json          (config gerado pelo build)
        ├── tiles/                 (24 tiles .gph - motor)
        ├── tiles_backup/          (copia limpa pre-injecao, restauravel)
        ├── traffic_csvs/          (CSVs de tile com h(e) codificado)
        └── traffic_report/        (auditoria: summary.json + affected_edges.csv)
```

## Componentes

### Valhalla (motor de roteamento)

- Imagem: `ghcr.io/valhalla/valhalla:latest` (v3.6.3)
- Porta: 8002
- Carrega os tiles de `data/tiles/` em memória
- Endpoints relevantes: `/route`, `/locate`, `/trace_attributes`
- Tile build: feito uma vez em `build/docker-compose.build.yml` a partir do `.pbf`
- Tiles **são modificados in-place** quando rodamos `valhalla_add_predicted_traffic` (por isso o `tiles_backup/`)

### PostGIS (banco de dados)

- Imagem: `postgis/postgis:16-3.4`
- Porta: 5432
- Inicializa com extensão PostGIS habilitada (script em `runtime/initdb/01-postgis.sql`)
- Volume nomeado `postgis_data` (persistente)
- Tabelas criadas no init (`runtime/initdb/02-tables.sql`):
  - `alagamentos_realtime` (snapshot atual do CGE)
  - `geocode_cache` (resultados do Nominatim cacheados)

### Nominatim (geocoder)

- Imagem: `mediagis/nominatim:4.4`
- Porta: 8080
- Atrás de profile `geocoding` — não sobe no `docker compose up` padrão
- Usa o mesmo `.pbf` do Valhalla (montado apenas o arquivo, fora de `/nominatim/` para evitar o `chown -R` do init.sh, ver [07 — Quirks](07-quirks-e-decisoes.md))
- Import inicial leva **alguns minutos** para o recorte da RMSP e ocupa ~3-5 GB de disco (sem flatnode — ver [Quirk #7](07-quirks-e-decisoes.md))
- Substitui o uso de Google Maps Geocoding API do scraper original

### Backend (FastAPI) — **implementado** (Etapa 3)

- Imagem própria (`backend/Dockerfile`, python:3.12-slim), sobe no `docker compose up` padrão na porta 8000
- Stack: FastAPI + SQLAlchemy 2 + asyncpg (PostGIS) + httpx (Valhalla/Nominatim) + pydantic v2
- Endpoints: `POST /rota`, `GET/POST /alagamentos` (+ `/snapshot`), `POST /geocode`, `GET /health`
- Traduz `chuva: bool` → `date_time` (quirk #1) e monta `exclude_locations` a partir do PostGIS
- Detalhes em [06 — API](06-api-valhalla.md)

### Frontend (React + Leaflet) — **a fazer**

Ver [09 — Roadmap](09-roadmap.md).

### Scraper CGE-SP — **implementado** (Etapa 4)

- Imagem própria (`scraper/Dockerfile`), atrás do profile `scraper` — rodado sob demanda em batch
- Código de partida: <https://github.com/vitor-yuichi/cge_scrapper>, recriado nos padrões do projeto
- Selenium + Chromium headless coleta o HTML do CGE-SP; BeautifulSoup faz o parse
- Geocoder Google Maps original substituído pelo Nominatim local (via backend `/geocode`, com cache no PostGIS)
- Pipeline: scrape → parse → geocode → `POST /alagamentos/snapshot` (aborta se 0 registros, pra não limpar o DB)
- Polling automático ainda **a fazer** (Etapa 6) — hoje é disparo manual

## Fluxo de dados — exemplo de request de rota

1. Usuário no frontend escolhe origem, destino e marca "está chovendo"
2. Frontend envia `POST /rota {origem, destino, chuva: true}` para o backend FastAPI
3. Backend:
   - Lê `alagamentos_realtime` no PostGIS (pontos ativos do CGE)
   - Monta payload Valhalla:
     - `locations: [origem, destino]`
     - `exclude_locations: [...pontos do CGE...]` ← b(e) = ∞
     - `date_time: {type: 1, value: "<hoje>T13:00"}` ← força modo "constrained" (chuva)
     - `alternates: 3`
   - Envia para Valhalla `:8002/route`
4. Valhalla executa A* nos tiles (com speeds penalizadas para hotspots, h(e) codificado nos tiles)
5. Backend retorna 1-3 rotas ao frontend
6. Frontend desenha no mapa

## Fluxo de atualização dos pesos históricos

Quando um novo shapefile histórico for entregue pela equipe (ou após um rebuild dos tiles):

```powershell
# use --force-backup após um rebuild (o backup antigo seria de outro .pbf)
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py --force-backup
```

Esse script faz tudo:

1. Backup dos tiles em `data/tiles_backup/` (`--force-backup` sobrescreve o existente)
2. Lê o shapefile, filtra `INTRANSITAVEL`, geocodifica via `/locate` do Valhalla
3. Agrupa em CSVs por tile, calcula `speed = original / (1 + h/Q)`
4. Roda `valhalla_add_predicted_traffic` dentro do container
5. Reinicia o container `valhalla` para recarregar tiles em memória
6. Roda smoke test (rota seco vs chuva) e mostra a penalidade efetiva

Detalhes em [05 — Pipeline de tráfego](05-pipeline-trafego.md).
