# 09 — Roadmap

O que já está pronto, o que falta, e em que ordem fazer.

## Estado atual (2026-06-10)

```
[✓] Etapa 0  — Validação técnica do Valhalla (binários, tiles, traffic.tar)
[✓] Etapa 1  — Infraestrutura base (compose com valhalla + postgis + nominatim)
[✓] Etapa 2  — Pipeline ERMAC -> Valhalla (build_traffic_csvs + refresh_traffic)
[✓] Etapa 3  — Backend FastAPI (/health, /geocode, /alagamentos, /rota)
[✓] Etapa 4  — Scraper CGE-SP + integração Nominatim + push snapshot
[✓] Etapa 5  — Frontend (React + Vite + Leaflet) — MVP core (rota + alagamentos)
[✓] Documentação operacional (esta pasta)
[ ] Etapa 6  — Modo polling automático do scraper (real-time)
[ ] Etapa 7  — Monitoramento (Prometheus/Grafana ou equivalente)
[ ] Etapa 8  — Deploy em ambiente compartilhado
```

> Recorte do mapa migrado de Sudeste → **região metropolitana de SP** em 2026-06-08 (ver [04 — Infraestrutura](04-infraestrutura.md) e Quirk #7).

## Etapa 3 — Backend FastAPI

**Objetivo:** expor um HTTP REST que recebe origem/destino/chuva e devolve rotas.

### Endpoints planejados

| Método | Rota | Descrição |
|---|---|---|
| POST | `/rota` | Recebe `{origem, destino, chuva}`. Lê alagamentos do PostGIS, monta payload Valhalla (com `exclude_locations` + `date_time`), devolve 1 a 3 rotas. |
| GET | `/alagamentos` | Lista pontos atualmente ativos do CGE (do PostGIS). |
| POST | `/geocode` | Proxy para Nominatim, com cache no PostGIS. |
| POST | `/scraper/run` | Trigger manual do scraper CGE-SP (em fase 3 vira automático). |
| GET | `/health` | Status agregado dos serviços. |

### Stack escolhida
- **FastAPI** (Python 3.11+)
- **SQLAlchemy 2 + asyncpg** para PostGIS
- **pydantic v2** para validação de payload
- **httpx** para chamar Valhalla/Nominatim
- **uvicorn** como ASGI server

### Estrutura sugerida
```
backend/
├── pyproject.toml
├── README.md
├── Dockerfile
├── src/
│   ├── main.py              # FastAPI app
│   ├── routers/
│   │   ├── rota.py
│   │   ├── alagamentos.py
│   │   ├── geocode.py
│   │   └── scraper.py
│   ├── services/
│   │   ├── valhalla.py      # cliente HTTP do Valhalla
│   │   ├── nominatim.py     # cliente HTTP do Nominatim + cache
│   │   └── ermac.py         # logica chuva/seco, alternates, ranking
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations/      # alembic
│   └── schemas/             # pydantic models
└── tests/
```

### Schemas iniciais do PostGIS

```sql
CREATE TABLE alagamentos_realtime (
    id SERIAL PRIMARY KEY,
    endereco_raw TEXT,
    bairro TEXT,
    referencia TEXT,
    sentido TEXT,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_Point(lng, lat), 4326)) STORED,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_alagamentos_geom ON alagamentos_realtime USING GIST (geom);
CREATE INDEX idx_alagamentos_active ON alagamentos_realtime (resolved_at) WHERE resolved_at IS NULL;

CREATE TABLE geocode_cache (
    endereco_norm TEXT PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Etapa 4 — Adaptar scraper CGE-SP

Repo de partida: <https://github.com/vitor-yuichi/cge_scrapper>.

### Mudanças necessárias

1. **De batch histórico → modo "agora":** trocar `extract_floods_cge(inicio, final)` por `extract_floods_now()` (passa data de hoje).
2. **Geocoder Google Maps → Nominatim:** substituir `googlemaps.Client.geocode()` por chamada HTTP ao nosso Nominatim local.
3. **Persistência:** em vez de salvar em Excel, gravar em `alagamentos_realtime` com diff (first_seen, last_seen, resolved_at).
4. **Estrutura como serviço:** containerizar (`Dockerfile`), expor como worker rodável sob demanda ou em loop.

Estrutura sugerida:

```
scraper/
├── pyproject.toml
├── Dockerfile
├── src/
│   ├── cge.py               # Selenium scraping
│   ├── geocoder.py          # Nominatim client
│   ├── pipeline.py          # scrape -> geocode -> diff -> persist
│   └── cli.py               # entrypoint: scrapper run [--once|--loop]
└── tests/
```

## Etapa 5 — Frontend ✅ (MVP core)

Stack implementada (`frontend/`):

- **React 18 + Vite** + **react-leaflet/Leaflet**
- **@mapbox/polyline** para decodificar o shape das rotas (**precisão 6** — ver abaixo)
- Servido por **nginx** num container (`docker-compose`), com proxy reverso `/api → backend:8000` (sem CORS). Publicado em `localhost:3000`.

### Funcionalidades entregues

- **Definir origem/destino** de 3 formas: endereço (geocodado pelo backend), **clique no mapa** (1º origem, 2º destino, 3º reinicia) ou **GPS** ("Minha localização")
- **4 rotas por condição** (combinações de chuva × alagamento), cada uma em uma cor:
  - 🟢 sem chuva/sem alagamento (ideal), 🔵 com chuva, 🟠 com alagamento, 🔴 pior caso
  - O front chama `POST /rota` 4× com `(chuva, evitar_alagamentos)` ∈ {false,true}² (`alternates: 0`)
  - **Legenda = controle de visibilidade** (clicar liga/desliga a rota); mostra distância e tempo
  - Sobreposições legíveis via espessuras concêntricas (pior por baixo → ideal por cima)
  - Requer o param `evitar_alagamentos` no backend (adicionado nesta etapa)
- **Camada de hotspots históricos** (pesos estáticos) com toggle — círculos coloridos por severidade `h(e)`, servidos por `GET /hotspots` (novo endpoint que lê `affected_edges.csv`)
- Marcadores dos **alagamentos ativos do CGE** (`GET /alagamentos`)
- **Pinos** de origem (verde) e destino (roxo) em formato de gota
- **Seletor de mapa base** com miniaturas de preview: OSM, Claro (CartoDB), Escuro (CartoDB), Satélite (Esri)
- Mimos: botão **Limpar**, overlay **"Calculando…"**, barra de **escala**, controles de **zoom**
- Interface modernizada e **responsiva** (em mobile o painel vira bottom sheet)

> **Atenção ao integrar:** o Valhalla codifica o `shape` com **precisão 6**, não a 5 padrão. Decodificar com `polyline.decode(shape, 6)` — precisão errada distorce a rota. Ver `frontend/src/lib/polyline.js`.

### Deixado para depois

- Heatmap contínuo (hoje os hotspots são círculos por severidade)
- Reverse-geocoding dos pontos definidos por clique/GPS (hoje usam coordenadas direto)
- TanStack Query / cache de estado (hoje é `fetch` + `useState`, suficiente para o MVP)

## Etapa 6 — Polling automático do scraper

Tornar o scraper autônomo, com cadência adaptativa:

- **5 min** em condições normais
- **2 min** se há ≥ 1 alagamento ativo
- **15 min** após 1h sem alagamentos
- Retry com exponential backoff em caso de erro de scraping
- Alerta se falhar por >15 min (período crítico)

Implementação como container `scraper-worker` no compose, com healthcheck.

## Etapa 7 — Monitoramento

- Métricas no backend FastAPI (latência, error rate, request count)
- Métricas custom: % de rotas que usaram alternativas, distância média poupada por desvio, etc.
- Logs estruturados (JSON) para fácil parsing
- Dashboard com tudo agregado

Stack sugerido: Prometheus + Grafana + Loki, ou OpenTelemetry → vendor.

## Etapa 8 — Deploy

- Definir alvo (servidor próprio, AWS, GCP, etc.)
- CI/CD (GitHub Actions) para build/push das imagens
- Migração da stack atual → ambiente compartilhado
- DNS + TLS (Caddy ou Nginx + Let's Encrypt)
- Autenticação no backend (JWT ou API keys)
- Rate limiting
- Backup automático (cron)

## Ideias para depois

- **Integração com CEMADEN:** complementa o CGE-SP cobrindo Brasil inteiro (paper original).
- **Modelo ML para previsão:** dado tempo + histórico recente, prever próximos pontos de alagamento.
- **Push notifications:** alertar usuários frequentes em rotas afetadas.
- **API pública:** se o sistema for útil, expor para outras prefeituras adaptarem (Rio, BH, etc.).
- **Validação científica:** comparar rotas resilientes vs Google Maps em eventos reais, publicar resultados.
- **App mobile (offline-first):** tiles pré-baixados + sync periódico — útil em emergências com rede instável.

## O que NÃO vai entrar (provavelmente)

- Roteamento multimodal (pé + ônibus + carro)
- Suporte a outras cidades além de SP (sem dados históricos comparáveis)
- Predição de severidade do alagamento (precisa muito mais dado)
