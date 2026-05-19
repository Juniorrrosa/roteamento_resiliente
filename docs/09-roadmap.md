# 09 — Roadmap

O que já está pronto, o que falta, e em que ordem fazer.

## Estado atual (2026-05-18)

```
[✓] Etapa 0  — Validação técnica do Valhalla (binários, tiles, traffic.tar)
[✓] Etapa 1  — Infraestrutura base (compose com valhalla + postgis + nominatim)
[✓] Etapa 2  — Pipeline ERMAC -> Valhalla (build_traffic_csvs + refresh_traffic)
[✓] Documentação operacional (esta pasta)
[ ] Etapa 3  — Backend FastAPI
[ ] Etapa 4  — Adaptação do scraper CGE-SP + integração com Nominatim
[ ] Etapa 5  — Frontend (React + Leaflet/MapLibre)
[ ] Etapa 6  — Modo polling automático do scraper (real-time)
[ ] Etapa 7  — Monitoramento (Prometheus/Grafana ou equivalente)
[ ] Etapa 8  — Deploy em ambiente compartilhado
```

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

## Etapa 5 — Frontend

Stack sugerida:

- **React 18 + Vite** ou **Next.js 14** (App Router)
- **Leaflet** (maduro, simples) ou **MapLibre GL JS** (mais bonito, tiles vetoriais)
- **TanStack Query** para state server-side

### Funcionalidades MVP

- Input de origem (geocoding via backend `/geocode`)
- Input de destino (idem)
- Toggle "está chovendo"
- Botão "Calcular rota"
- Mapa com:
  - Linha da rota principal (azul)
  - Linhas das alternativas (cinza)
  - Marcadores dos alagamentos atuais (CGE)
  - Heatmap dos hotspots históricos (opcional)
- Painel com: distância, tempo estimado, "evita N alagamentos"

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
