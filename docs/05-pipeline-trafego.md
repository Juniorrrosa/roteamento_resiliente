# 05 — Pipeline de tráfego (ERMAC → Valhalla)

Este é o pipeline que transforma o shapefile histórico de alagamentos em pesos por aresta dentro dos tiles do Valhalla.

## TL;DR

> ⚠️ **Windows com Smart App Control (SAC) / WDAC:** a política do Windows bloqueia as DLLs nativas do GDAL usadas pelo `geopandas`/`pyogrio`, então rodar o pipeline no **Python do host falha** com `ImportError: ... An Application Control policy has blocked this file`. Nesse caso use o **Caminho A (Docker)** abaixo. Detalhes em [07 — Quirk #8](07-quirks-e-decisoes.md).

### Caminho A — via Docker (recomendado no Windows)

Roda a leitura do shapefile num contêiner Linux (onde a política do Windows não se aplica), depois injeta e reinicia:

```powershell
# 1. gera os CSVs de pesos dentro de um conteiner, na rede do Valhalla
docker run --rm --network roteamento-resiliente_roteamento -v "${PWD}:/work" -w /work python:3.12-slim `
  sh -c "pip install -q geopandas pyogrio requests && python scripts/build_traffic_csvs.py --clean --q 10.0 --valhalla-url http://valhalla:8002"

# 2. injeta nos tiles e reinicia
docker exec valhalla valhalla_add_predicted_traffic -c /data/valhalla.json /data/traffic_csvs
docker restart valhalla
```

Para trocar `Q`, ajuste o `--q` no passo 1. Para re-gerar após um rebuild do `.pbf`, faça um backup manual dos tiles limpos antes (ver [Restaurar tiles](#restaurar-tiles-limpos-antes-da-injeção)) — o `refresh_traffic.py` faz isso sozinho, mas ele não roda no host com SAC.

### Caminho B — via Python no host (Linux/macOS, ou Windows sem SAC)

```powershell
# preparacao (uma vez)
python -m venv scripts\.venv
.\scripts\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt pyogrio

# rodar (sempre que o shapefile mudar OU se quiser reinjetar)
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py
```

> `scripts/requirements.txt` traz `geopandas`, mas o backend de leitura (`pyogrio` ou `fiona`) precisa ser instalado à parte — daí o `pyogrio` no `pip install` acima.

Saída esperada do `refresh_traffic.py` (~15 segundos):

```
INFO | Pontos INTRANSITAVEL: 922 / 2154 total
INFO | Arestas unicas afetadas: 879
INFO | CSVs gerados: 4 (total 879 arestas)
INFO | valhalla> Updated 879 directed edges.
INFO | reiniciando container valhalla
INFO | healthy em 5.6s
INFO | seco  (T03:00, free_flow):   length=0.239km time=26.4s
INFO | chuva (T13:00, constrained): length=0.239km time=53.3s
INFO | fidelidade ERMAC ok: penalidade efetiva = +102.0%
```

## Anatomia do pipeline

```
shapefile (Alag-Inun_2015-2025.shp)
    │
    │  geopandas + filtro CONDICAO=INTRANSITAVEL + reprojecao EPSG:4326
    ▼
922 pontos (lat, lon)
    │
    │  POST /locate em batches de 50, recolhe edge_id + default_speed + length
    ▼
879 arestas distintas {(level, tile_id, id) -> EdgeRecord}
    │
    │  agrupa por tile, calcula constrained = default / (1 + h/Q)
    ▼
4 arquivos CSV em data/traffic_csvs/<level>/.../<id>.csv
    │
    │  docker exec valhalla valhalla_add_predicted_traffic -c valhalla.json <csv_dir>
    ▼
tiles .gph modificados in-place (Updated 879 directed edges)
    │
    │  docker restart valhalla (tiles em memoria sao recarregados)
    ▼
smoke test: rota seco vs chuva no mesmo trecho
```

## Quando re-rodar

Os comandos abaixo assumem o **Caminho B** (host). No Windows com SAC, use o **Caminho A** (Docker) e ajuste os flags equivalentes no `build_traffic_csvs.py`.

| Trigger | Comando (Caminho B) |
|---|---|
| Shapefile histórico atualizado (nova versão da equipe) | `python scripts/refresh_traffic.py` |
| Quer ajustar `Q` (sensibilidade) | `python scripts/refresh_traffic.py --q 5` |
| Após `valhalla_build_tiles` (re-build do .pbf) | `python scripts/refresh_traffic.py --force-backup` (o backup antigo está desatualizado) |
| Só inspecionar relatórios sem mexer em nada | `python scripts/build_traffic_csvs.py --summary-only` |
| Re-gerar CSVs sem injetar (debug) | `python scripts/refresh_traffic.py --no-restart` (gera CSVs e injeta mas não reinicia) — ou só `python scripts/build_traffic_csvs.py` |

## Os scripts

### `scripts/build_traffic_csvs.py`

Faz só a parte do Python: lê shapefile, consulta `/locate`, escreve CSVs e relatórios. **Não toca nos tiles**.

Argumentos:

```
--shapefile PATH      shapefile (default: modelo_py/Alag-Inun_2015-2025.shp)
--condition VAL       valor da coluna CONDICAO a filtrar (default: INTRANSITAVEL)
--valhalla-url URL    URL do Valhalla (default: http://localhost:8002)
--output PATH         pasta de CSVs (default: data/traffic_csvs)
--report-dir PATH     pasta de relatórios (default: data/traffic_report)
--q FLOAT             fator Q do paper (default: 10.0)
--max-distance FLOAT  raio máximo de snap em metros (default: 200.0)
--batch-size INT      pontos por request /locate (default: 50)
--timeout FLOAT       timeout por request, segundos (default: 120)
--clean               apaga a pasta de CSVs antes de escrever
--summary-only        só roda /locate e gera relatórios; não escreve CSVs
-v, --verbose
```

### `scripts/refresh_traffic.py`

Wrapper end-to-end. Orquestra: backup → build CSVs → injeta → restart → smoke test.

Argumentos:

```
--container NAME       nome do container Valhalla (default: valhalla)
--valhalla-url URL     URL pública (default: http://localhost:8002)
--q FLOAT              fator Q (default: 10.0)
--python PATH          python da venv (default: scripts/.venv/Scripts/python.exe)
--skip-backup          não copia data/tiles → data/tiles_backup
--force-backup         sobrescreve backup existente
--no-restart           injeta mas não reinicia o container
--no-smoke             pula o smoke test final
```

## Saídas geradas

### `data/traffic_csvs/`

Estrutura espelha a dos tiles:

```
data/traffic_csvs/
├── 0/001/473.csv      (333 arestas — level 0)
├── 1/023/893.csv      (332 arestas — level 1)
└── 2/000/382/
    ├── 133.csv        (208 arestas — level 2)
    └── 134.csv        (6 arestas — level 2)
```

Cada CSV é texto puro:

```
edge_id,free_flow_kmh,constrained_kmh
0/1473/94745,50,45
0/1473/94765,50,45
...
```

### `data/traffic_report/summary.json`

Sumário usado para auditoria e diagnóstico:

```json
{
  "q": 10.0,
  "total_edges": 879,
  "h_distribution": { "1": 499, "2": 151, ... },
  "max_h": 32,
  "worst_case_speed_ratio": 0.238
}
```

### `data/traffic_report/affected_edges.csv`

Tabela detalhada das 879 arestas, ordenada por `h` decrescente. Cada linha tem:

- `level`, `tile_id`, `edge_id`
- `h` (contagem de pontos)
- `default_speed_kmh`, `length_m`
- `way_id` (OSM way que originou a aresta — útil pra debug no JOSM/iD)
- `correlated_lat`, `correlated_lon` (onde a aresta está no mapa)
- `penalized_speed_kmh`, `speed_ratio`

Útil para abrir no QGIS ou Excel e inspecionar visualmente onde estão os hotspots.

## Troubleshooting

### "shapefile sem coluna CONDICAO"

A coluna `CONDICAO` é esperada — se o shapefile que veio da equipe tem outro nome (ex: `condicao`, `Condition`, `STATUS`), use `--condition <valor>` e edite o script. O `modelo_py/novo_modelo.py` original usa exatamente `CONDICAO == 'INTRANSITAVEL'`.

### `valhalla_add_predicted_traffic: Configuration is required`

Você passou `-c PATH` mas o positional arg `<traffic_dir>` faltou ou veio depois de `-c` colado. A ordem correta:

```
valhalla_add_predicted_traffic -c /data/valhalla.json /data/traffic_csvs
                                                     ^ positional
```

(O wrapper `refresh_traffic.py` já está correto.)

### `Updated 0 directed edges`

Geralmente:

1. CSV com **4 colunas** (3ª é vírgula vazia) — o tool tenta decodificar a 4ª como DCT-II e falha → ignora a linha. Use 3 colunas exatas.
2. Caminho `<traffic_dir>` errado ou vazio.
3. Os `edge_id` no CSV não existem nos tiles atuais (rebuild dessincronizou).

### Healthcheck do Valhalla fica `unhealthy` após restart

Tiles muito grandes ou disco lento — pode levar até ~60s para carregar. Se persistir, ver `docker logs valhalla` para ver se há erro de "tile not found" ou similar.

### Smoke test não mostra diferença de tempo seco vs chuva

Significa que o trecho testado **não atravessa nenhuma das 879 arestas afetadas**. Os parâmetros do smoke test no `refresh_traffic.py` apontam para a região da pior aresta (~-23.569, -46.608) — se você mudou de shapefile e os hotspots foram pra outra região, ajuste as coordenadas em `refresh_traffic.py:smoke_test()`.

### Restaurar tiles "limpos" (antes da injeção)

```powershell
cd runtime
docker compose down
Remove-Item -Recurse ..\data\tiles
Copy-Item -Recurse ..\data\tiles_backup ..\data\tiles
docker compose up -d
```

Em seguida, se quiser reinjetar:

```powershell
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py --skip-backup
```

(`--skip-backup` porque o backup atual já é o estado limpo.)
