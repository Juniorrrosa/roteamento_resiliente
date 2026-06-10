# Backend — Roteamento Resiliente

API HTTP que orquestra Valhalla, PostGIS e Nominatim para entregar rotas conforme o modelo ERMAC.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Status agregado (Valhalla / Nominatim / Postgres) |
| `POST` | `/geocode` | Endereço → lat/lon (Nominatim com cache no PostGIS) |
| `GET` | `/alagamentos` | Lista alagamentos ativos (resolved_at IS NULL) |
| `POST` | `/alagamentos/snapshot` | Substitui o snapshot ativo (usado pelo scraper) |
| `DELETE` | `/alagamentos/{id}` | Marca um alagamento como resolvido |
| `POST` | `/rota` | Calcula rotas. Params: `origem`, `destino`, `chuva`, `evitar_alagamentos` (default `true`), `alternates` |
| `GET` | `/hotspots` | Hotspots históricos (pesos estáticos): lat/lng + h(e) por aresta, de `affected_edges.csv` |

Documentação interativa: `http://localhost:8000/docs` (Swagger UI).

## Rodar local (com auto-reload)

Pré-requisitos: Valhalla, PostGIS e Nominatim já rodando via `runtime/docker-compose.yml`.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env       # edite a senha do Postgres se mudou

# rodar
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Em Linux/macOS, substitua `.\.venv\Scripts\` por `./.venv/bin/`.

## Rodar via Docker compose

O serviço `backend` já está em `runtime/docker-compose.yml`. Ele sobe junto com Valhalla e PostGIS:

```powershell
cd runtime
docker compose up -d backend
docker compose logs -f backend
```

## Configuração

Variáveis de ambiente (ver `.env.example`):

| Var | Default local | Default em compose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://roteamento:...@localhost:5432/roteamento` | `...@postgis:5432/...` |
| `VALHALLA_URL` | `http://localhost:8002` | `http://valhalla:8002` |
| `NOMINATIM_URL` | `http://localhost:8080` | `http://nominatim:8080` |
| `ERMAC_Q` | `10.0` | `10.0` |
| `LOG_LEVEL` | `INFO` | `INFO` |
| `CORS_ORIGINS` | `*` | `*` |
| `HOTSPOTS_CSV` | `/data/traffic_report/affected_edges.csv` | idem (via mount `../data:/data:ro`) |

> O endpoint `/hotspots` lê o relatório `affected_edges.csv` gerado por `scripts/refresh_traffic.py`. No compose, o backend monta `../data:/data:ro` para acessá-lo.

## Estrutura

```
backend/
├── pyproject.toml         deps + setup
├── Dockerfile             imagem de produção (multi-stage)
├── .env.example           template de variáveis
├── app/
│   ├── main.py            FastAPI app + lifespan
│   ├── config.py          settings via pydantic-settings
│   ├── db.py              SQLAlchemy async + ORM models
│   ├── schemas.py         pydantic DTOs (request/response)
│   ├── valhalla.py        cliente HTTP do Valhalla
│   ├── nominatim.py       cliente Nominatim + geocode cache
│   └── routers/
│       ├── health.py
│       ├── geocode.py
│       ├── alagamentos.py
│       ├── rota.py
│       └── hotspots.py
└── tests/
    └── test_smoke.py      sanity checks de endpoints
```

## Modelo ERMAC dentro do backend

`POST /rota` recebe `{origem, destino, chuva, evitar_alagamentos, alternates}`. Internamente:

1. Se `origem.endereco` (string) foi fornecido em vez de `lat/lon`, geocodifica via `/geocode`
2. Se `evitar_alagamentos` (default `true`), lê `alagamentos_realtime` ativos do PostGIS; se `false`, ignora-os (usado para gerar as variantes "sem alagamento" no front)
3. Monta payload Valhalla:
   - `locations`: origem + destino
   - `exclude_locations`: pontos do CGE → implementa **b(e) = ∞** do paper (omitido quando `evitar_alagamentos=false`)
   - `date_time`: `T03:00` (modo seco) ou `T13:00` (modo chuva) — implementa o **switch ERMAC**
   - `alternates`: 0 a 3
4. Devolve rotas com geometria, distância, tempo, e nº de exclusões aplicadas

> O front usa essas duas flags para desenhar **4 cenários** (chuva × alagamento): chamadas paralelas com `(chuva, evitar_alagamentos)` ∈ {false,true}².

Detalhes da decisão `date_time` em [`docs/07-quirks-e-decisoes.md`](../docs/07-quirks-e-decisoes.md).

## Sem autenticação (fase 1)

Esta fase do backend não tem auth. Em produção, **não expor a porta 8000 diretamente** — colocar atrás de reverse proxy com auth. Ver `docs/08-deploy.md`.
