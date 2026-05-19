# 04 — Infraestrutura

Tudo é orquestrado por `runtime/docker-compose.yml`. Três serviços, um deles atrás de profile.

## Serviços

| Serviço | Imagem | Porta | Sobre no `up` padrão? | Volumes |
|---|---|---|---|---|
| `valhalla` | `ghcr.io/valhalla/valhalla:latest` | 8002 | ✅ | `../data:/data` |
| `postgis` | `postgis/postgis:16-3.4` | 5432 | ✅ | `postgis_data` + `./initdb` |
| `nominatim` | `mediagis/nominatim:4.4` | 8080 | ❌ (profile `geocoding`) | só o `.pbf` montado + 2 volumes nomeados |

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
| nominatim | `curl http://localhost:8080/status` | **horas** durante o import inicial; depois ~60s |

Durante o import inicial do Nominatim, o status fica `unhealthy` mas o container está rodando normalmente. **Não reiniciar** — vai recomeçar do zero. Acompanhe via `docker logs -f nominatim`.

## Estrutura `data/`

```
data/
├── sudeste-latest.osm.pbf  (799 MB — OSM bruto)
├── valhalla.json            (config gerado pelo build)
├── tiles/                   (1.07 GB — tiles ativos do Valhalla)
├── tiles_backup/            (1.07 GB — copia pré-injeção)
├── valhalla/                (symlink/alias de tiles)
├── traffic_csvs/            (~50 KB — CSVs ERMAC, regenerados sob demanda)
└── traffic_report/          (summary.json + affected_edges.csv — auditoria)
```

Total de disco usado: ~3-5 GB sem Nominatim. Com Nominatim importado (Sudeste, medido em 2026-05-19):

- `nominatim_data` (Postgres com índice): **~14 GB**
- `nominatim_flatnode` (cache de nodes OSM): **~110 GB**
- Total adicional: **~124 GB**

O `flatnode` é alocado de forma esparsa (sparse file) — o tamanho lógico é grande mas o uso real em alguns filesystems pode ser menor. Em volumes Docker no Windows/macOS (Hyper-V VHD), o tamanho lógico é o que conta.

## Re-build dos tiles do Valhalla (quando trocar o `.pbf`)

Caso baixe um `.pbf` novo do <https://download.geofabrik.de/>:

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

O build leva ~10-30 minutos dependendo da máquina. Sobrescreve `data/tiles/` e `data/valhalla.json`.

> **Atenção:** após um rebuild, os pesos ERMAC injetados são **perdidos**. Roda `python scripts/refresh_traffic.py` em seguida para reinjetar.

## Rede

Todos os serviços usam a rede nomeada `roteamento` (compose nomeia automaticamente como `roteamento-resiliente_roteamento`). Eles se comunicam pelos hostnames:

- `valhalla:8002`
- `postgis:5432`
- `nominatim:8080`

Quando o backend FastAPI subir no compose, ele vai usar esses hostnames. Para acesso externo (testes manuais), use `localhost:<porta>`.

## Considerações de RAM/CPU

| Serviço | RAM em idle | RAM em uso típico | CPU |
|---|---|---|---|
| valhalla | ~1.5 GB | 2-3 GB (tile cache) | baixa, picos no /route |
| postgis | ~200 MB | até `shared_buffers` | baixa |
| nominatim | ~500 MB | 1-2 GB | alta durante import (multi-thread), baixa depois |

Em uma máquina de dev (8 GB RAM): tudo cabe. Em produção: dimensionar conforme volume de requisições.

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

O volume `nominatim_data` representa horas de importação. **Faça snapshot do volume** se for migrar de máquina:

```powershell
docker run --rm -v roteamento-resiliente_nominatim_data:/data -v ${PWD}:/backup alpine `
  tar czf /backup/nominatim_data.tar.gz -C /data .
```
