# 06 — API do Valhalla

O Valhalla expõe uma API HTTP em `http://localhost:8002`. Os endpoints relevantes para o nosso uso:

- `/route` — calcula a rota entre pontos
- `/locate` — encontra a(s) aresta(s) mais próxima(s) de um ponto
- `/trace_attributes` — analisa propriedades de uma rota dada (polyline)
- `/status` — health check

Documentação oficial completa: <https://valhalla.github.io/valhalla/api/>.

Este doc mostra os parâmetros que importam **para o nosso modelo ERMAC**.

## /route — calcular uma rota

Endpoint: `POST /route`

### Payload mínimo

```json
{
  "locations": [
    {"lat": -23.580, "lon": -46.620},
    {"lat": -23.540, "lon": -46.580}
  ],
  "costing": "auto"
}
```

### Payload completo para o nosso uso

```json
{
  "locations": [
    {"lat": -23.580, "lon": -46.620},
    {"lat": -23.540, "lon": -46.580}
  ],
  "costing": "auto",
  "exclude_locations": [
    {"lat": -23.568, "lon": -46.608},
    {"lat": -23.557, "lon": -46.629}
  ],
  "alternates": 2,
  "date_time": {"type": 1, "value": "2026-05-18T13:00"}
}
```

### Parâmetros que importam

#### `locations`
Array com pelo menos 2 pontos: origem e destino. Cada ponto é `{lat, lon}`. Pode ter waypoints intermediários (3+ pontos).

#### `costing`
Modo de transporte. Para nós: sempre `"auto"` (carro). Outros disponíveis: `bicycle`, `pedestrian`, `truck`, etc. — não usamos por enquanto.

#### `exclude_locations` — implementa `b(e) = ∞`
Array de pontos a evitar. Cada ponto faz com que arestas próximas sejam removidas do grafo antes da busca. Este é o mecanismo do **alagamento em tempo real**: o backend lê os pontos ativos do CGE no PostGIS e injeta aqui.

> Atenção: se **todas as rotas possíveis** passarem por um ponto excluído, o Valhalla devolve a melhor rota possível ignorando a exclusão (graciosamente), não um erro. O backend pode detectar isso comparando a rota retornada com a lista de exclusões.

#### `alternates`
Número de rotas alternativas além da principal. Default 0. Para o modelo ERMAC original (3 alternativas), use `"alternates": 2` (1 principal + 2 alternativas = 3 totais). Valor máximo prático: 3.

#### `date_time` — implementa o flag "chuva ON/OFF"

Este é o parâmetro **mais importante** e mais sutil. Veja [07 — Quirks](07-quirks-e-decisoes.md) para entender porque controla o switch chuva/seco.

```json
{"type": 1, "value": "2026-05-18T03:00"}   // modo SECO (free_flow_speed)
{"type": 1, "value": "2026-05-18T13:00"}   // modo CHUVA (constrained_speed)
```

- `type: 1` = depart_at (saída no instante dado)
- `value`: ISO 8601, formato `YYYY-MM-DDThh:mm`
- Horário **noturno** (~22h–06h) → Valhalla usa `free_flow_speed` → modo seco
- Horário **diurno** (~07h–21h) → Valhalla usa `constrained_speed` → modo chuva

O backend FastAPI deve aceitar `chuva: bool` no payload do `/rota` e gerar o `date_time` apropriado internamente.

### Response

```json
{
  "trip": {
    "summary": {
      "length": 11.288,      // km
      "time": 961.0,         // segundos
      "min_lat": ..., "max_lat": ...,
      "min_lon": ..., "max_lon": ...
    },
    "legs": [
      {
        "shape": "encoded polyline (precision 1e-6)",
        "maneuvers": [...]
      }
    ]
  },
  "alternates": [
    { "trip": { "summary": {...}, "legs": [...] } }
  ]
}
```

O `shape` é uma polyline codificada em **precision 6** (1e-6). Para decodificar em JS use `@mapbox/polyline` com `precision: 6`. Em Python: ver função `decode()` em `scripts/refresh_traffic.py:smoke_test` (versões antigas) ou usar `polyline.decode(s, precision=6)`.

## /locate — informações sobre uma localização

Endpoint: `POST /locate`

### Payload

```json
{
  "locations": [{"lat": -23.5685, "lon": -46.6079}],
  "costing": "auto",
  "verbose": true
}
```

### Response (para o nosso uso)

```json
[
  {
    "input_lat": -23.5685,
    "input_lon": -46.6079,
    "edges": [
      {
        "distance": 5.2,                 // metros até a aresta
        "correlated_lat": -23.56843,
        "correlated_lon": -46.60789,
        "edge_id": {
          "level": 1,
          "tile_id": 23893,
          "id": 85966,
          "value": 4704837739946
        },
        "edge_info": {
          "way_id": 128190711,           // OSM way id
          "speed_limit": 0
        },
        "edge": {
          "speeds": {
            "default": 50,
            "free_flow": 50,             // injetado pelo nosso pipeline
            "constrained_flow": 12,      // injetado pelo nosso pipeline
            "predicted": false
          },
          "geo_attributes": {
            "length": 45                 // metros
          }
        }
      }
    ]
  }
]
```

Usamos `/locate` no pipeline `build_traffic_csvs.py` para encontrar a aresta correspondente a cada ponto histórico do shapefile.

## /trace_attributes — debug por aresta

Endpoint: `POST /trace_attributes`

Útil para **verificar quais velocidades estão sendo aplicadas em cada aresta de uma rota**.

### Payload

```json
{
  "encoded_polyline": "<shape do /route>",
  "costing": "auto",
  "date_time": {"type": 1, "value": "2026-05-18T13:00"},
  "filters": {
    "attributes": ["edge.way_id", "edge.speed", "edge.length"],
    "action": "include"
  }
}
```

### Response

```json
{
  "edges": [
    {"way_id": 944310443, "speed": 45, "length": 0.058},
    {"way_id": 128190711, "speed": 12, "length": 0.045},
    ...
  ]
}
```

Se um edge no nosso `traffic_report/affected_edges.csv` está com `constrained_speed=12` e o `trace_attributes` com `date_time=13:00` mostra `speed=12`, a injeção pegou. Se mostra `50`, algo está errado (talvez não restartou o container).

## /status — healthcheck

```bash
curl http://localhost:8002/status
```

```json
{"version": "3.6.3", "tileset_last_modified": 1747234... }
```

Usado pelo healthcheck do compose.

## Limites e gotchas

- **Timeouts:** para Sudeste inteiro, requests muito longas (>500 km) podem demorar segundos. O `valhalla_service` tem 1 worker por padrão (`valhalla_service /data/valhalla.json 1`) — para produção, aumentar.
- **Concorrência:** ajustar workers em produção (`docker run ... 4` para 4 workers).
- **`alternates` máx:** 3. Pedir mais não dá erro, mas pode devolver menos do que pedido.
- **`exclude_polygons`:** alternativa a `exclude_locations` para áreas (em vez de pontos). Pode ser útil para zonas inundadas grandes — verificar a sintaxe na doc oficial se for usar.
- **Tarifa de pedágio, faixas exclusivas, transit:** Valhalla suporta, mas não usamos no escopo atual.

## Exemplos curl prontos pra colar

```bash
# rota simples
curl -X POST http://localhost:8002/route -H 'Content-Type: application/json' -d '{
  "locations":[{"lat":-23.5695,"lon":-46.6080},{"lat":-23.5675,"lon":-46.6078}],
  "costing":"auto"
}'

# rota modo chuva com 2 alternates
curl -X POST http://localhost:8002/route -H 'Content-Type: application/json' -d '{
  "locations":[{"lat":-23.5695,"lon":-46.6080},{"lat":-23.5675,"lon":-46.6078}],
  "costing":"auto",
  "date_time":{"type":1,"value":"2026-05-18T13:00"},
  "alternates":2
}'

# rota chuva evitando pontos
curl -X POST http://localhost:8002/route -H 'Content-Type: application/json' -d '{
  "locations":[{"lat":-23.5695,"lon":-46.6080},{"lat":-23.5675,"lon":-46.6078}],
  "costing":"auto",
  "date_time":{"type":1,"value":"2026-05-18T13:00"},
  "exclude_locations":[{"lat":-23.568,"lon":-46.608}]
}'

# inspecionar uma aresta
curl -X POST http://localhost:8002/locate -H 'Content-Type: application/json' -d '{
  "locations":[{"lat":-23.5685,"lon":-46.6079}],"costing":"auto","verbose":true
}'

# status
curl http://localhost:8002/status
```
