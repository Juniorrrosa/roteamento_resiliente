# 08 — Deploy e operação em produção

> Status atual: o projeto está em fase de desenvolvimento. Esta página descreve **como pretendemos fazer o deploy** e quais cuidados tomar quando chegar a hora.

## Pré-requisitos do host

| Recurso | Mínimo dev | Recomendado produção |
|---|---|---|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16–32 GB (Valhalla + Nominatim + Postgres) |
| Disco | 20 GB | **200 GB SSD** (Nominatim sozinho ocupa ~124 GB — 14 GB de Postgres + 110 GB de flatnode) |
| OS | Linux/macOS/Windows com Docker Desktop | Linux com Docker Engine |
| Docker | 24+ com Compose v2 | 24+ |

## Fluxo de deploy do zero

1. **Clonar o repo** e configurar Git
2. **Baixar o .pbf** do Geofabrik (uma vez):
   ```bash
   mkdir -p data
   curl -L -o data/sudeste-latest.osm.pbf \
        https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf
   ```
3. **Build dos tiles do Valhalla** (uma vez, ~10–30 min):
   ```bash
   cd build && docker compose -f docker-compose.build.yml up && cd ..
   ```
4. **Configurar `.env`:**
   ```bash
   cp runtime/.env.example runtime/.env
   # editar runtime/.env com senhas REAIS (não as do .env.example)
   ```
5. **Subir os serviços base:**
   ```bash
   cd runtime && docker compose up -d
   ```
6. **Preparar venv do pipeline ERMAC:**
   ```bash
   python -m venv scripts/.venv
   ./scripts/.venv/bin/python -m pip install -r scripts/requirements.txt
   ```
7. **Injetar pesos históricos:**
   ```bash
   ./scripts/.venv/bin/python scripts/refresh_traffic.py
   ```
8. **(Opcional) Subir Nominatim** (import ~3-4h para Sudeste; ocupa ~124 GB depois — 14 GB de Postgres + 110 GB de flatnode):
   ```bash
   cd runtime && docker compose --profile geocoding up -d nominatim
   docker logs -f nominatim
   ```
9. **Smoke test:**
   ```bash
   curl -X POST http://localhost:8002/route -H 'Content-Type: application/json' \
        -d '{"locations":[{"lat":-23.5695,"lon":-46.6080},{"lat":-23.5675,"lon":-46.6078}],"costing":"auto","date_time":{"type":1,"value":"2026-05-18T13:00"}}'
   ```

## Gestão de secrets

**Nunca commitar `runtime/.env`** — está no `.gitignore`. O `runtime/.env.example` é commitado como template.

Para produção:

- Gere senhas longas (32+ chars) com `openssl rand -base64 32`
- Não use as senhas do `.env.example`
- Em ambientes orquestrados (Kubernetes, ECS, Swarm), use o sistema de secrets nativo (Kubernetes Secrets, AWS Secrets Manager, etc.) em vez do arquivo `.env`

## Backups

### Tiles do Valhalla

- `data/tiles_backup/` é criado pelo `refresh_traffic.py` na primeira execução — representa o estado pós-build mas **pré-injeção ERMAC**
- Para fazer snapshot completo (tiles + traffic_csvs + reports):
  ```bash
  tar czf valhalla_snapshot_$(date +%Y%m%d).tar.gz data/tiles data/traffic_csvs data/traffic_report data/valhalla.json
  ```

### PostGIS

```bash
docker exec postgis pg_dump -U roteamento -F c roteamento > backup_$(date +%Y%m%d).dump
```

Restore:

```bash
docker exec -i postgis pg_restore -U roteamento -d roteamento --clean < backup_YYYYMMDD.dump
```

Recomendado: backup diário automático via cron + rotação de 7–30 dias.

### Nominatim

O volume `nominatim_data` é o mais crítico (horas de import). Para snapshot:

```bash
docker run --rm -v roteamento-resiliente_nominatim_data:/data -v $(pwd):/backup alpine \
    tar czf /backup/nominatim_data_$(date +%Y%m%d).tar.gz -C /data .
```

Para restaurar em outra máquina:

```bash
docker volume create roteamento-resiliente_nominatim_data
docker run --rm -v roteamento-resiliente_nominatim_data:/data -v $(pwd):/backup alpine \
    tar xzf /backup/nominatim_data_YYYYMMDD.tar.gz -C /data
```

## Atualização do shapefile histórico

Quando a equipe de pesquisa entregar uma versão atualizada do shapefile:

1. Substituir o arquivo em `modelo_py/Alag-Inun_2015-2025.shp` (e os auxiliares `.dbf`, `.shx`, `.prj`, `.cpg`, `.qmd`)
2. Rodar:
   ```bash
   ./scripts/.venv/bin/python scripts/refresh_traffic.py
   ```
3. O wrapper faz backup automático antes (se ainda não houver), gera CSVs novos, injeta e roda smoke test

Tempo total: ~15 segundos (não conta o backup inicial dos tiles, que leva ~1 min na primeira vez).

## Atualização do `.pbf` (re-build dos tiles)

Quando OpenStreetMap evoluir significativamente (semanalmente o Geofabrik atualiza), pode valer re-build:

1. Baixar `.pbf` novo
2. Rodar `build/docker-compose.build.yml` (sobrescreve `data/tiles/`)
3. **IMPORTANTE:** re-rodar `python scripts/refresh_traffic.py --force-backup` — o backup antigo é dos tiles antigos
4. Reinjetar pesos ERMAC (parte do `refresh_traffic.py`)

## Monitoramento sugerido

Métricas críticas para ter em produção:

| Métrica | Limite de alerta |
|---|---|
| `valhalla:8002/status` HTTP 200 | <1 min de downtime |
| Latência p95 `/route` | <500 ms |
| Erros 5xx no backend | >1% |
| Fila do scraper CGE travada | >15 min sem coleta (em fase 3) |
| Espaço em disco | <10% livre |
| Memória do container `valhalla` | >80% |

Sugestão de stack: Prometheus + Grafana, ou stack equivalente (Datadog, etc.).

## Considerações de segurança

- **Valhalla**: o serviço por default não tem autenticação. **Não expor a porta 8002 diretamente para a internet** — só atrás do backend FastAPI (que adiciona auth/rate-limit) ou de um reverse proxy (Caddy/Nginx) com auth.
- **PostGIS**: mesmo princípio. Senha forte + acesso só de dentro da rede do compose.
- **Nominatim**: aceita queries sem auth. Mesma recomendação — não expor diretamente.
- **Atualizações**: revisar mensalmente se há atualizações das imagens (`docker pull` + rebuild).
- **Dependências Python**: rodar `pip-audit` periodicamente no `scripts/requirements.txt`.

## Logs

- `docker compose logs <serviço>` — logs em tempo real (`-f` para follow, `--tail N`)
- Volume default do Docker para logs (`json-file driver`) pode crescer. Em produção, configurar `max-size` no `daemon.json` ou usar `journald`:
  ```yaml
  # em docker-compose.yml de cada serviço
  logging:
    driver: json-file
    options:
      max-size: "50m"
      max-file: "5"
  ```

## Procedimento para incidente

### Valhalla sem resposta

1. `docker ps` — container está rodando?
2. `docker logs valhalla --tail 100` — última erro?
3. `docker restart valhalla` — restart simples (10s)
4. Se persistir: `cd runtime && docker compose down && docker compose up -d`
5. Se ainda persistir: restaurar de backup (`data/tiles_backup → data/tiles`)

### PostGIS sem resposta

1. `docker logs postgis --tail 100`
2. `docker exec postgis pg_isready -U roteamento -d roteamento`
3. Se corrupção: restaurar do dump mais recente

### Nominatim degradado

1. Verificar disco — Nominatim usa muito
2. `docker logs nominatim --tail 200`
3. Restart só funciona se o import já terminou; senão recomeça do zero — ter cuidado

## Migração para outra máquina

Em ordem:

1. Parar a stack antiga (`docker compose down`)
2. Snapshot dos volumes (PostGIS, Nominatim, etc.)
3. Copiar `data/`, `runtime/.env`, `scripts/.venv` (não — recriar na nova máquina)
4. Na nova máquina: clonar repo, restaurar volumes, recriar venv, rodar `docker compose up -d`
5. Smoke test antes de redirecionar tráfego
