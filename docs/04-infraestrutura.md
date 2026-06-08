# 04 — Infraestrutura

Tudo é orquestrado por `runtime/docker-compose.yml`. Cinco serviços, dois atrás de profile.

## Serviços

| Serviço | Imagem | Porta | Sobre no `up` padrão? | Volumes |
|---|---|---|---|---|
| `valhalla` | `ghcr.io/valhalla/valhalla:latest` | 8002 | ✅ | `../data:/data` |
| `postgis` | `postgis/postgis:16-3.4` | 5432 | ✅ | `postgis_data` + `./initdb` |
| `backend` | build `../backend` (FastAPI) | 8000 | ✅ | — |
| `nominatim` | `mediagis/nominatim:4.4` | 8080 | ❌ (profile `geocoding`) | só o `.pbf` montado + `nominatim_data` (sem flatnode) |
| `scraper` | build `../scraper` (CGE-SP) | — | ❌ (profile `scraper`, batch) | — |

## Variáveis de ambiente

Arquivo: `runtime/.env` (gitignored). Template em `runtime/.env.example`:

```env
POSTGRES_DB=roteamento
POSTGRES_USER=roteamento
POSTGRES_PASSWORD=troque-esta-senha
NOMINATIM_PASSWORD=troque-esta-senha
```

O `docker-compose.yml` usa `${POSTGRES_PASSWORD:?defina ... em runtime/.env}`, que falha cedo se a variável não estiver definida.

## Comandos do dia a dia

```powershell
cd runtime

# subir base (valhalla + postgis)
docker compose up -d

# parar e remover containers (mantém volumes)
docker compose down

# subir tambem o nominatim (so a 1a vez ou apos terminar import)
docker compose --profile geocoding up -d nominatim

# logs em tempo real
docker compose logs -f valhalla
docker compose logs -f nominatim   # util durante o import

# reiniciar um servico (ex: depois de injetar trafego)
docker compose restart valhalla

# status com healthcheck
docker compose ps
docker ps --format 'table {{.Names}}\t{{.Status}}'

# zerar tudo (containers + volumes — perde dados do postgis!)
docker compose down -v
```

## Healthchecks

Cada serviço expõe um healthcheck. `docker compose up -d` retorna assim que os containers sobem; o healthcheck transiciona de `starting` → `healthy` (ou `unhealthy`).

| Serviço | Check | Tempo típico p/ healthy |
|---|---|---|
| valhalla | `wget http://localhost:8002/status` | ~30s (carrega tiles em RAM) |
| postgis | `pg_isready -U $USER -d $DB` | ~10s |
| nominatim | `curl http://localhost:8080/status` | **~3 min** durante o import inicial (RMSP); depois ~60s |

Durante o import inicial do Nominatim, o status fica `unhealthy` mas o container está rodando normalmente. **Não reiniciar** — vai recomeçar do zero. Acompanhe via `docker logs -f nominatim`.

## Estrutura `data/`

```
data/
├── sao-paulo.osm.pbf        (137 MB — OSM bruto, recorte RMSP)
├── valhalla.json            (config gerado pelo build)
├── tiles/                   (128 MB — tiles ativos do Valhalla)
├── tiles_backup/            (128 MB — copia pré-injeção)
├── valhalla/                (symlink/alias de tiles)
├── traffic_csvs/            (~50 KB — CSVs ERMAC, regenerados sob demanda)
└── traffic_report/          (summary.json + affected_edges.csv — auditoria)
```

> O `.pbf` é um recorte da **região metropolitana de SP** (bbox `-47.05,-24.05,-46.15,-23.25`), gerado a partir do `sudeste-latest.osm.pbf` com `osmium extract`. Ver README para o comando.

Total de disco usado: ~0.5 GB sem Nominatim. Com Nominatim importado (RMSP, medido em 2026-06-08):

- `nominatim_data` (Postgres com índice + nós): **~3-5 GB**
- Total adicional: **~3-5 GB**

> **Importante — sem flatnode.** Não montamos o volume `nominatim_flatnode`. Se montado, a imagem ativa o `flatnode.file` do osm2pgsql, que ocupa **~110 GB fixos** (dimensionado pelo maior node ID global do OSM, não pelo recorte). Para extratos urbanos vale mais guardar os nós no Postgres — ver [Quirk #7](07-quirks-e-decisoes.md). O flatnode só compensa em imports de planeta/continente.

## Re-gerar o recorte do `.pbf` (mudar área de cobertura)

O Geofabrik não tem recorte municipal/estadual — só macrorregiões. Para gerar o `.pbf` de SP, baixe o Sudeste e recorte com `osmium`:

```powershell
cd data
# 1. baixar o Sudeste (~800 MB) — só se ainda nao tiver
curl -L -o sudeste-latest.osm.pbf https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf

# 2. recortar a RMSP (ajuste a bbox p/ outra area se quiser)
docker run --rm -v ${PWD}:/data stefda/osmium-tool `
  osmium extract -b -47.05,-24.05,-46.15,-23.25 --strategy smart `
  /data/sudeste-latest.osm.pbf -o /data/sao-paulo.osm.pbf
```

`--strategy smart` evita ways/relações truncadas na borda (importante p/ roteamento). O recorte leva ~1-2 min.

## Re-build dos tiles do Valhalla (quando trocar o `.pbf`)

```powershell
# 1. apontar o nome correto no build/docker-compose.build.yml (se mudar)
# 2. rodar o build
cd build
docker compose -f docker-compose.build.yml up

# 3. quando terminar, voltar pra runtime e subir
cd ..\runtime
docker compose down
docker compose up -d
```

O build da RMSP leva ~3-4 minutos. Sobrescreve `data/tiles/` e `data/valhalla.json`.

> **Atenção:** após um rebuild, os pesos ERMAC injetados são **perdidos**. Roda `python scripts/refresh_traffic.py --force-backup` em seguida para reinjetar (o `--force-backup` garante que o `tiles_backup/` reflita o `.pbf` novo).

## Rede

Todos os serviços usam a rede nomeada `roteamento` (compose nomeia automaticamente como `roteamento-resiliente_roteamento`). Eles se comunicam pelos hostnames:

- `valhalla:8002`
- `postgis:5432`
- `backend:8000`
- `nominatim:8080`

O backend FastAPI (no compose) usa esses hostnames internos. Para acesso externo (testes manuais), use `localhost:<porta>`.

## Considerações de RAM/CPU

Valores aproximados com o recorte da RMSP (tiles de 128 MB, bem menores que o Sudeste):

| Serviço | RAM em idle | RAM em uso típico | CPU |
|---|---|---|---|
| valhalla | ~0.3-0.5 GB | ~0.5-1 GB (tile cache) | baixa, picos no /route |
| postgis | ~200 MB | até `shared_buffers` | baixa |
| backend | ~150 MB | ~150-300 MB | baixa |
| nominatim | ~500 MB | 1-2 GB | alta durante import (~3 min), baixa depois |

Em uma máquina de dev (8 GB RAM): tudo cabe com folga. Em produção: dimensionar conforme volume de requisições.

## Backup e restauração

### Tiles

Backup feito pelo `refresh_traffic.py` na primeira execução, em `data/tiles_backup/`. Para restaurar manualmente:

```powershell
docker compose down
Remove-Item -Recurse data/tiles
Copy-Item -Recurse data/tiles_backup data/tiles
docker compose up -d
```

### PostGIS

```powershell
# dump
docker exec postgis pg_dump -U roteamento roteamento > backup_$(Get-Date -Format yyyyMMdd).sql

# restore
docker exec -i postgis psql -U roteamento -d roteamento < backup_YYYYMMDD.sql
```

### Nominatim

O volume `nominatim_data` (~4 GB) guarda o import. Reimportar é rápido (~3 min para a RMSP), mas dá pra snapshotar pra migrar de máquina sem reimportar:

```powershell
docker run --rm -v roteamento-resiliente_nominatim_data:/data -v ${PWD}:/backup alpine `
  tar czf /backup/nominatim_data.tar.gz -C /data .
```
