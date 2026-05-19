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
                      │ Backend (TODO)  │
                      │ FastAPI         │
                      │  /rota          │
                      │  /alagamentos   │
                      │  /geocode       │
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
        │  tiles Sudeste                           │  data: PBF
        │  (1.07 GB)                               │  (799 MB)
        │  + speeds                                │  importacao:
        │  injetadas                               │  ~30-50 GB
        ▼                                          ▼
        ────────── volume: ./data/ ──────────
        ├── sudeste-latest.osm.pbf  (.pbf OSM bruto, lido por Valhalla e Nominatim)
        ├── valhalla.json          (config gerado pelo build)
        ├── tiles/                 (1547 .gph - tiles do motor)
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
- Vai armazenar:
  - `alagamentos_realtime` (snapshot atual do CGE)
  - `geocode_cache` (resultados do Nominatim cacheados)
  - Outras tabelas conforme o backend FastAPI for sendo desenvolvido

### Nominatim (geocoder)

- Imagem: `mediagis/nominatim:4.4`
- Porta: 8080
- Atrás de profile `geocoding` — não sobe no `docker compose up` padrão
- Usa o mesmo `.pbf` do Valhalla (montado apenas o arquivo, fora de `/nominatim/` para evitar o `chown -R` do init.sh, ver [07 — Quirks](07-quirks-e-decisoes.md))
- Import inicial **leva horas** para Sudeste e ocupa ~30-50 GB de disco
- Substitui o uso de Google Maps Geocoding API do scraper original

### Backend (FastAPI) — **a fazer**

Ver [09 — Roadmap](09-roadmap.md).

### Frontend (React + Leaflet) — **a fazer**

Ver [09 — Roadmap](09-roadmap.md).

### Scraper CGE-SP — **a adaptar**

Código de partida: <https://github.com/vitor-yuichi/cge_scrapper>. Em fase 1, rodado manualmente em batch. Geocoder original (Google Maps) será substituído por Nominatim local.

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

Quando um novo shapefile histórico for entregue pela equipe:

```powershell
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py
```

Esse script faz tudo:

1. Backup dos tiles (na primeira vez)
2. Lê o shapefile, filtra `INTRANSITAVEL`, geocodifica via `/locate` do Valhalla
3. Agrupa em CSVs por tile, calcula `speed = original / (1 + h/Q)`
4. Roda `valhalla_add_predicted_traffic` dentro do container
5. Reinicia o container `valhalla` para recarregar tiles em memória
6. Roda smoke test (rota seco vs chuva) e mostra a penalidade efetiva

Detalhes em [05 — Pipeline de tráfego](05-pipeline-trafego.md).
