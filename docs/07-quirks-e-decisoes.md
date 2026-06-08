# 07 — Quirks e decisões técnicas

## Quirk #1 — Valhalla: o switch chuva/seco é via `date_time`, não `speed_types`

### O que esperávamos
A documentação do Valhalla descreve dois mecanismos para escolher qual velocidade usar:

1. `speed_types: ["freeflow" | "constrained" | "predicted" | "current"]` no payload do `/route`
2. `costing_options.auto.flow_mask: 1|2|4|8` (bitmask: 1=freeflow, 2=constrained, ...)

Tentamos os dois para controlar via API a aplicação ou não do peso `h(e)`.

### O que aconteceu

Validamos empiricamente na versão **3.6.3** da imagem `ghcr.io/valhalla/valhalla:latest`:

| Configuração | Velocidade usada na pior aresta (default=50, constrained=12) |
|---|---|
| `speed_types: ["freeflow"]` | 12 (constrained) ❌ |
| `speed_types: ["constrained"]` | 12 (constrained) ✓ |
| `flow_mask: 1` | crash do serviço (Connection reset) ❌ |
| `flow_mask: 2` | 12 (constrained) ✓ |
| `flow_mask: 0` | 12 (constrained) ❌ (deveria usar default) |
| `date_time` em 03:00 | 50 (free_flow) ✓ |
| `date_time` em 13:00 | 12 (constrained) ✓ |

**Conclusão:** `speed_types` e `flow_mask` não fazem o que a doc sugere. O Valhalla escolhe entre `free_flow_speed` e `constrained_speed` baseado no **horário do dia em `date_time`**.

- Noite (~22h–06h) → `free_flow_speed`
- Dia (~07h–21h) → `constrained_speed`

O crash com `flow_mask: 1` é porque populamos `free_flow` para apenas 879 das ~milhões de arestas — para as outras, `free_flow = 0`, divisão por zero ao calcular tempo. (Não testamos no fundo da pilha; pode ser bug do Valhalla nessa versão.)

### Como contornamos

O backend FastAPI recebe `chuva: bool` do cliente e gera o `date_time` correto:

```python
def date_time_for_chuva(chuva: bool) -> dict:
    today = date.today().isoformat()
    hour = "13:00" if chuva else "03:00"
    return {"type": 1, "value": f"{today}T{hour}"}
```

### Dívida técnica

Esse hack acopla **horário do dia** com **estado de chuva**. Se um dia precisarmos de roteamento sensível ao horário real (rush-hour, etc.), o acoplamento quebra. Possíveis evoluções futuras:

- Atualizar para uma versão mais nova do Valhalla onde `speed_types` funcione (testar e validar antes)
- Migrar para `historical_speeds` (DCT-II encoded), que tem flag `use_predicted_speeds` própria
- Manter dois containers Valhalla (decisão revertida em 2026-05-18 — ver memória)

Registrado em `~/.claude/projects/.../memory/project_valhalla_speed_switch_quirk.md`.

## Quirk #2 — Nominatim: `chown -R /nominatim` falha em mount read-only

### O sintoma
Nominatim crashloop com `chown: changing ownership of '/nominatim/data/...': Read-only file system` e exit code 1. Importação **nunca começa**.

### A causa
O `init.sh` da imagem `mediagis/nominatim` faz `chown -R nominatim:nominatim /nominatim`. Se montamos `../data:/nominatim/data:ro`, esse chown falha → `set -e` derruba o script.

### A correção
Montar **apenas o arquivo .pbf** num caminho **fora de `/nominatim/`**:

```yaml
volumes:
  - ../data/sao-paulo.osm.pbf:/pbf/sao-paulo.osm.pbf:ro   # <- fora de /nominatim/
environment:
  PBF_PATH: /pbf/sao-paulo.osm.pbf
```

Assim o `chown -R /nominatim` não toca no arquivo (que é read-only por causa do mount).

## Quirk #3 — Valhalla CSV: 4ª coluna vazia causa "Updated 0 directed edges"

O `valhalla_add_predicted_traffic` aceita até 4 colunas:
```
edge_id, free_flow_speed, constrained_speed, historical_speeds_DCT2
```

Se gerarmos com a 4ª coluna **vazia** (`edge_id,50,45,`), o tool **tenta decodificar a string vazia** como DCT-II e:

```
[WARN] Invalid compressed speeds in file: 0/001/473.csv line 1; error='Decoded speed string size expected= 400 actual=72057594037927935'
...
[INFO] Updated 0 directed edges.
```

Linhas com decode inválido são **ignoradas**. Solução: gerar CSV com **exatamente 3 colunas** (sem vírgula trailing).

Aplicado em `scripts/build_traffic_csvs.py` na função `write_traffic_csvs`.

## Quirk #4 — `valhalla_add_predicted_traffic`: `<traffic_dir>` é positional, não `-t`

A documentação informal e alguns issues sugerem `-t <dir>`. Olhando o `--help` da v3.6.3:

```
Usage: valhalla_add_predicted_traffic [OPTION...] Traffic tile dir
```

`Traffic tile dir` é **positional**, sem flag. O comando correto:

```bash
valhalla_add_predicted_traffic -c /data/valhalla.json /data/traffic_csvs
                                                     ^ positional aqui
```

Curiosamente, `-t /data/traffic_csvs` "funciona" em alguns contextos (provavelmente o parser argpars do C++ é lenient), mas em `docker exec` direto retorna `Configuration is required`. Sempre use a forma positional.

## Quirk #5 — Tiles são modificados in-place; precisa restart pra ver

`valhalla_add_predicted_traffic` modifica os arquivos `.gph` em `data/tiles/`. Mas o `valhalla_service` carrega tudo em RAM no startup e **não relê**. Para o efeito ser visível:

```bash
docker restart valhalla
```

`docker exec valhalla supervisorctl reload` **não basta** — precisa o restart do PID 1.

O wrapper `refresh_traffic.py` faz isso automaticamente.

## Quirk #6 — PowerShell mata o exit code de comandos nativos com `2>&1`

No Windows PowerShell 5.1, redirecionar stderr de exe nativos (docker, valhalla_*) com `2>&1` faz o PowerShell tratar cada linha de stderr como NativeCommandError, mesmo com exit 0. Resultado: scripts parecem falhar quando não falharam.

Solução: **não use `2>&1`** com executáveis nativos no PowerShell. Deixe stderr ir naturalmente. Se precisar capturar, use no Bash via `docker exec <c> bash -c "... 2>&1"` (o redirect é interpretado dentro do bash do container, não no PowerShell).

## Quirk #7 — Nominatim: o flatnode ocupa ~110 GB independente do tamanho do recorte

### O sintoma
Trocamos o `.pbf` do Sudeste (799 MB) por um recorte da RMSP (137 MB) esperando que o Nominatim encolhesse proporcionalmente. O Postgres encolheu (14 GB → ~3 GB), mas o `nominatim_flatnode` continuou em **~103 GB reais** (arquivo totalmente alocado, não esparso).

### A causa
O `flatnode.file` do osm2pgsql é um array indexado pelo **maior node ID global do OSM** (~13,7 bilhões), a 8 bytes por slot → ~110 GB. O tamanho depende do espaço de IDs do OSM, **não** da quantidade de dados do recorte. Um extrato pequeno preserva os IDs globais originais, então o flatnode fica do mesmo tamanho.

### A correção
A imagem `mediagis/nominatim` só ativa o flatnode **se existir o diretório `/nominatim/flatnode`** (lógica em `/app/config.sh`):

```bash
if [ -d "${PROJECT_DIR}/flatnode" ]; then sed -i 's|...NOMINATIM_FLATNODE_FILE=...="/nominatim/flatnode/flatnode.file"|' ...; fi
```

Basta **não montar** o volume `nominatim_flatnode`. Sem o diretório, `NOMINATIM_FLATNODE_FILE` fica vazio e o osm2pgsql guarda as coordenadas dos nós nas slim tables do Postgres — para a RMSP isso é pequeno (total do Nominatim cai para ~3-5 GB).

O flatnode só compensa em imports grandes (planeta/continente), onde o overhead de I/O do Postgres para bilhões de nós seria proibitivo. Para recortes urbanos, **não use flatnode**.

## Decisões registradas

### Por que Valhalla e não NetworkX?

O `modelo_py/novo_modelo.py` original usa OSMnx + NetworkX + A* (sem Valhalla). Razão: protótipo acadêmico que opera numa bbox pequena de SP. Para produção:

- NetworkX em SP inteira é lento (segundos por rota)
- Valhalla na região metropolitana é rápido (~10-100ms por rota)
- A fórmula ERMAC é representável no Valhalla com fidelidade — ver [03 — Modelo matemático](03-modelo-matematico.md)

Decisão: Valhalla (1 container, escopo região metropolitana de SP).

### Por que 1 container Valhalla e não 2 (dry/wet)?

Originalmente planejamos 2 containers — um com pesos injetados (chuva) e outro sem (seco). Ao descobrir que `speed_types` deveria funcionar nativamente, simplificamos para 1 container.

Quando descobrimos que `speed_types` na verdade **não funciona** e o switch é via `date_time`, mantivemos 1 container porque:

- Tile com `free_flow` (= original) + `constrained` (= penalizado) → mesma estrutura
- Backend troca `date_time` por request, sem precisar de 2 containers
- Economiza ~2 GB RAM e ~1 GB disco

### Por que Nominatim e não Google Maps Geocoding?

- Mesmo `.pbf` do Valhalla (zero custo de dado adicional)
- Latência local (~10–50 ms) vs API Google (~200–500 ms)
- Sem custo recorrente, sem chave de API, sem rate limit
- Trade-off: ~10–20% pior em endereços brasileiros informais ("esquina com", "embaixo do viaduto")
- Estratégia: começar com Nominatim puro; se a qualidade frustar, adicionar Google como fallback condicional

### Por que CGE-SP e não CEMADEN?

O paper ERMAC cita CEMADEN como fonte de tempo real. Optamos por CGE-SP porque:

- Já existe scraper Selenium pronto (<https://github.com/vitor-yuichi/cge_scrapper>)
- Cobertura: cidade de SP (que é o escopo prático do projeto)
- CEMADEN tem cobertura nacional mas requer investigar como acessar
- Em uma fase futura, podemos integrar ambos

### Por que `scripts/.venv` e não conda/poetry/uv?

- Stdlib `venv` é zero-dep, funciona em qualquer Python 3
- Requirements simples (geopandas + requests) — não justifica ferramenta mais sofisticada
- Caso o time prefira poetry/uv no futuro, é fácil migrar (`scripts/requirements.txt` é a fonte da verdade)
