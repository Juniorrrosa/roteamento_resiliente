# 03 — Modelo matemático e evidências empíricas

## A fórmula original

Do paper, página 1:

> Define-se a função `b: E → {1, ∞}` que indica se a aresta está alagada agora:
> - `b(e) = 1` se a aresta **não** está alagada
> - `b(e) = ∞` caso contrário
>
> `h(e)` indica o número de vezes que a aresta foi fechada por alagamento no histórico, `l(e)` é o comprimento físico da aresta, e `Q ∈ ℝ` é um fator de calibração ajustável.
>
> A função peso `w: E → ℝ ∪ {∞}` é:
>
> ```
> w(e) = b(e) · (1 + h(e)/Q) · l(e)
> ```
>
> O peso total de um caminho é a soma dos pesos individuais. O algoritmo A* minimiza esse peso.

E na página 2:

> "Quando uma aresta não está alagada agora, mas está chovendo, seu peso é afetado pelo histórico de alagamento."

Ou seja, `h(e)` **só é aplicado quando está chovendo**. Em condições secas, `w(e) = b(e) · l(e)`.

## Mapeamento para o Valhalla

Valhalla otimiza sobre **tempo** (custo ∝ comprimento / velocidade), não sobre peso arbitrário. Mas existe uma equivalência matemática direta:

Se quisermos que o custo seja proporcional a `(1 + h(e)/Q) · l(e)`, basta **reduzir a velocidade efetiva** da aresta pelo mesmo fator:

```
speed_efetivo(e) = speed_original(e) / (1 + h(e)/Q)
```

Provando: `time(e) = l(e) / speed_efetivo(e) = l(e) · (1 + h(e)/Q) / speed_original(e)`. Como `speed_original(e)` é o mesmo para todas as arestas equivalentes do par origem-destino, ele é uma constante multiplicativa que não afeta o caminho ótimo. **A minimização de `time` no Valhalla é equivalente à minimização de `w(path)` do paper.**

### Tabela de mapeamento

| Elemento do paper | Implementação no Valhalla |
|---|---|
| `l(e)` | Atributo nativo `length` do tile (não precisa modificar) |
| `b(e) = ∞` (alagado em RT) | `exclude_locations` no payload do request (cada ponto vira um item; Valhalla evita arestas próximas) |
| `h(e)` | Pré-computado: para cada ponto histórico, `/locate` no Valhalla retorna a(s) aresta(s) mais próxima(s). Contamos quantas vezes cada aresta aparece. |
| `(1 + h(e)/Q)` | Aplicado como `constrained_speed = default_speed / (1 + h(e)/Q)` em CSV de tráfego, injetado nos tiles via `valhalla_add_predicted_traffic` |
| Flag chuva ON/OFF | `date_time` no request: noite → modo seco (usa `free_flow_speed` = original); dia → modo chuva (usa `constrained_speed` = penalizado). Ver [07 — Quirks](07-quirks-e-decisoes.md) para entender porque não usamos `speed_types`. |
| A* | Motor nativo do Valhalla (bidirectional A*, C++) |
| `W(path)` | Custo total devolvido em `trip.summary.time` |

### Esquema do CSV de tráfego

Cada CSV (uma por tile, em `data/traffic_csvs/<level>/<...>/<id>.csv`) tem o formato:

```
edge_id,free_flow_speed,constrained_speed
2/382133/321217,40,36
2/382133/321850,30,27
```

- `edge_id`: `<level>/<tile_id>/<local_id>` (formato canônico do Valhalla)
- `free_flow_speed`: km/h, **igual à velocidade original** (usado em modo seco)
- `constrained_speed`: km/h, **velocidade penalizada** = `floor(default / (1 + h/Q))`, mínimo 1

> **Atenção:** o tool `valhalla_add_predicted_traffic` aceita até 4 colunas (com `historical_speeds` em DCT-II). Se incluirmos a 4ª coluna vazia, o tool acusa "Invalid compressed speeds" e marca "Updated 0 directed edges". Por isso só geramos 3 colunas.

## Evidências empíricas — a fórmula realmente funciona?

Toda a validação abaixo é reproduzível com `python scripts/refresh_traffic.py` (smoke test embutido) + as queries curl deste documento.

### 1. Cobertura: 922 pontos históricos viraram 879 arestas afetadas

```
$ ./scripts/.venv/Scripts/python.exe scripts/build_traffic_csvs.py --summary-only

Pontos INTRANSITAVEL: 922 / 2154 total
batch 19/19 ok (22 pts)
Arestas unicas afetadas: 879
```

Note que 922 pontos viram 879 arestas — alguns pontos próximos snapam na mesma aresta (esperado em ruas com múltiplos registros históricos no mesmo trecho).

### 2. Distribuição de h(e)

```json
// data/traffic_report/summary.json
{
  "q": 10.0,
  "total_edges": 879,
  "h_distribution": {
    "1": 499,  "2": 151,  "3": 62,  "4": 46,  "5": 24,
    "6": 15,   "7": 14,   "8": 12,  "9": 8,   "10": 6,
    "11": 6,   "12": 13,  "13": 2,  "14": 2,  "15": 4,
    "16": 2,   "17": 4,   "18": 1,  "20": 2,  "24": 3,
    "26": 1,   "30": 1,   "32": 1
  },
  "max_h": 32,
  "worst_case_speed_ratio": 0.238
}
```

A maioria das arestas (499/879 = 57%) tem h=1. Algumas têm h alto (até 32 — provavelmente um ponto crítico recorrente da cidade, como uma marginal/baixa). Pior caso: velocidade reduzida a 23.8% da original.

### 3. Top 5 arestas mais penalizadas

Extraído de `data/traffic_report/affected_edges.csv`:

| level/tile/id | h | original (km/h) | penalizado (km/h) | razão | localização |
|---|---|---|---|---|---|
| 1/23893/85966 | 32 | 50 | 12 | 0.24 | (-23.5685, -46.6079) |
| 2/382133/309583 | 30 | 30 | 8  | 0.27 | (-23.5568, -46.6296) |
| 1/23893/90481 | 26 | 49 | 14 | 0.29 | (-23.5573, -46.6286) |
| 1/23893/90480 | 24 | 49 | 14 | 0.29 | (-23.5572, -46.6286) |
| 1/23893/90670 | 24 | 49 | 14 | 0.29 | (-23.5572, -46.6286) |

### 4. /locate confirma que as velocidades foram injetadas

```bash
$ curl -X POST http://localhost:8002/locate -H 'Content-Type: application/json' \
       -d '{"locations":[{"lat":-23.5685,"lon":-46.6079}],"costing":"auto","verbose":true}'
```

Resposta (recortada):

```json
{
  "edge_id": {"level": 1, "tile_id": 23893, "id": 85966},
  "edge": {
    "speeds": {
      "default": 50,
      "free_flow": 50,
      "constrained_flow": 12
    }
  }
}
```

O campo `default: 50` é a velocidade da classificação OSM original. Os campos `free_flow: 50` e `constrained_flow: 12` foram **injetados pelo nosso pipeline** — antes da injeção ambos eram 0.

### 5. /route mostra a diferença de tempo

Rota curta de 0.239 km sobre a pior aresta:

| `date_time` | tempo retornado | velocidade usada |
|---|---|---|
| `2026-05-18T03:00` (madrugada) | 26.4 s | `free_flow_speed = 50` |
| `2026-05-18T13:00` (meio-dia) | 53.3 s | `constrained_speed = 12` |

Tempo dobra (+102%) quando comutamos para o modo chuva. Reproduzível com:

```bash
for h in 03:00 13:00; do
  curl -sS -X POST http://localhost:8002/route -H 'Content-Type: application/json' \
    -d "{\"locations\":[{\"lat\":-23.5695,\"lon\":-46.6080},{\"lat\":-23.5675,\"lon\":-46.6078}],\"costing\":\"auto\",\"date_time\":{\"type\":1,\"value\":\"2026-05-18T$h\"}}" \
    | python -c "import sys,json; s=json.load(sys.stdin)['trip']['summary']; print(f'{s[\"time\"]:.1f}s')"
done
```

### 6. /route + exclude_locations muda a geometria da rota

Rota de 5km atravessando hotspots:

| Configuração | comprimento | tempo |
|---|---|---|
| modo seco (T03:00) | 11.288 km | 910.2 s |
| modo chuva (T13:00) | 11.288 km | 961.0 s (+5.6%) |
| modo chuva + exclude no meio | **10.537 km** | 925.8 s |

- A penalidade histórica (modo chuva sem exclude) **mantém a geometria** mas aumenta o tempo. O algoritmo não desvia porque o custo total ainda é menor pelo caminho original.
- Adicionar `exclude_locations` (b(e) = ∞ no paper) força mudança de geometria — rota nova evita a área proibida.

## Pontos de calibração

### O parâmetro Q

`Q` controla a sensibilidade ao histórico. Valor padrão é `Q = 10.0` (do `modelo_py/novo_modelo.py`). Efeito prático:

- `h(e) = 5, Q = 10` → penalidade = `1 + 5/10 = 1.5` (velocidade cai pra 67% da original)
- `h(e) = 5, Q = 5`  → penalidade = `1 + 5/5  = 2.0` (cai pra 50%)
- `h(e) = 5, Q = 20` → penalidade = `1 + 5/20 = 1.25` (cai pra 80%)

Para aumentar a sensibilidade (rotas desviam mais agressivamente): **diminuir Q**. Para suavizar: aumentar.

Re-rodar `python scripts/refresh_traffic.py --q 5` para experimentar.

### Raio de snap (`max_distance`)

Default: 200 m (igual ao `modelo_py`). Pontos do shapefile a mais de 200 m de qualquer aresta são ignorados.

```bash
python scripts/build_traffic_csvs.py --max-distance 100
```

Reduzir o raio gera menos arestas afetadas (mais precisão, menos diluição). Aumentar tem efeito oposto.

## O que NÃO é fiel ao paper

Algumas diferenças honestas que vale documentar:

1. **Direção da contagem de h(e):**
   - Paper / `modelo_py`: para cada aresta, conta quantos pontos históricos estão a ≤200 m do **centroide** da aresta.
   - Nossa implementação: para cada ponto histórico, pega a(s) aresta(s) mais próxima(s) via `/locate` do Valhalla.
   - Diferença: o paper conta um ponto para todas as arestas dentro de 200 m. Nós contamos uma vez por chamada `/locate` (que retorna tipicamente 1-2 arestas — uma para cada sentido de uma via mão-dupla).
   - Impacto: pequeno em vias retas; pode ser maior em interseções complexas. Não afeta a forma da fórmula, só a estimativa de `h(e)`.

2. **`b(e) = ∞`:**
   - Paper: peso literalmente infinito → caminho proibido absoluto.
   - Valhalla `exclude_locations`: tenta evitar; se todas as rotas passam pelo ponto, devolve a melhor rota possível em vez de erro. Tratamos isso no backend (a fazer).

3. **Calibração de Q:** Não temos validação empírica de qual Q reproduz melhor as escolhas de motoristas reais. O paper sugere "ajustável conforme a sensibilidade desejada".
