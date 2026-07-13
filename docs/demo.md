# Demo — roteiro de apresentação

Guia para demonstrar, ao vivo, que o motor de roteamento resiliente funciona de fato:
o modelo ERMAC tem **duas** componentes e esta página tem **uma demo para cada uma**.

| Componente | Fórmula | O que faz | Demo |
|---|---|---|---|
| **Restrição dura** `b(e)` | `b(e) ∈ {1, ∞}` | alagamento ativo agora → rota **não pode** passar | [Demo 1](#demo-1--restrição-dura-alagamento-em-tempo-real) |
| **Restrição suave** `h(e)/Q` | `w(e) = b(e)·(1 + h(e)/Q)·l(e)` | via com histórico → rota **prefere evitar** | [Demo 2](#demo-2--restrição-suave-peso-histórico) |

> Os dados de alagamento em tempo real usados aqui são **fictícios** (rótulo `FICTICIO-demo` no banco),
> inseridos via o mesmo endpoint que o scraper do CGE usa (`POST /alagamentos/snapshot`).
> O histórico (`h(e)`) é **real** — vem do shapefile `Alag-Inun_2015-2025.shp` já injetado nos tiles.

---

## Pré-requisitos

A stack precisa estar no ar (`cd runtime && docker compose --profile geocoding up -d`). Confira:

```powershell
curl http://localhost:8000/health     # deve responder {"status":"ok", ...}
```

Interface web: **http://localhost:3000**

Para (re)inserir os dados fictícios da Demo 1, rode o script do final desta página
([Apêndice C](#apêndice-c--rescript-dos-dados-fictícios)).

---

## Demo 1 — Restrição dura (alagamento em tempo real)

**Ideia:** dois pontos de alagamento bloqueiam as pontes diretas sobre o Rio Tietê.
Ao evitar alagamentos, a rota é obrigada a atravessar por **outra ponte** — desvio grande e visível.

**Passo a passo:**

1. Abra http://localhost:3000
2. Preencha o formulário:
   - **Origem:** `Avenida Casa Verde, 1500, São Paulo`
   - **Destino:** `Praça da República, São Paulo`
3. Clique em **Calcular**. O front calcula as 4 rotas (uma por cor):

   | Cor | Condição | evita alagamento? | Resultado |
   |---|---|---|---|
   | 🟢 Verde | Ideal (sem chuva, sem alagamento) | não | **5,63 km** — direto |
   | 🔵 Azul | Com chuva | não | 5,63 km (mesmo caminho) |
   | 🟠 Laranja | Sem chuva, com alagamento | **sim** | **7,99 km** — desvia |
   | 🔴 Vermelho | Pior caso (chuva + alagamento) | **sim** | 7,99 km — desvia |

4. **Ponto-chave:** compare a **🟢 verde (direto)** com a **🔴 vermelha (desviando)**.
   A vermelha atravessa o Tietê por outra ponte: **+2,36 km (+42%)**, porque as
   pontes diretas estão "alagadas".
   Use a **legenda como liga/desliga** para isolar uma rota de cada vez.
5. Ligue o toggle **"Histórico de alagamentos"** para mostrar os 879 hotspots
   e aponte os **8 marcadores de alagamento ativo** espalhados pela cidade.

**Números (medidos):**

```
SEM evitar alagamentos:  5,631 km / 473 s
COM evitar alagamentos:  7,993 km / 684 s   (8 alagamentos evitados)
>> DESVIO: +2,362 km (+42%), +210 s (~3,5 min)
```

---

## Demo 2 — Restrição suave (peso histórico)

**Ideia:** esta é a parte mais sutil e mais importante do paper. **Sem nenhum bloqueio**,
só pelo peso `h(e)/Q`, sob chuva o motor **aceita dirigir mais longe** para fugir de vias
historicamente alagadas. É a "preferência", não a "proibição".

**Passo a passo:**

1. Em http://localhost:3000, preencha:
   - **Origem:** `Praça Alberto Lion, Cambuci, São Paulo`
   - **Destino:** `Avenida do Estado, 7601, São Paulo`
2. Clique em **Calcular**.
3. **Ponto-chave:** compare a **🟢 verde (Ideal — sem chuva)** com a **🔵 azul (Com chuva)**.
   - Sem chuva, a rota segue o caminho **mais curto** (passa por vias com alto `h`).
   - Com chuva, o mesmo par origem/destino **muda de trajeto** e fica mais longo —
     o peso histórico tornou as vias alagáveis "caras", então o A\* prefere o contorno.
   - Aqui **`evitar_alagamentos` está irrelevante** (não há alagamento ativo nesse trecho):
     a mudança vem **exclusivamente** do `h(e)/Q`.

**Números (medidos):**

```
🟢 IDEAL (sem chuva):  2,639 km / 246 s   <- caminho curto, passa pelo histórico
🔵 CHUVA (com chuva):  3,967 km / 312 s   <- caminho mudou, contorna o histórico
>> DESVIO por peso histórico: +1,328 km (+50%)
```

> Dica de narrativa: "sem chuva o carro vai pelo caminho curto; quando começa a chover,
> o sistema sabe que aquelas ruas alagam e manda o motorista pelo desvio **antes** de
> chegar e encontrar água."

---

## Apêndice A — Evidências de validação do modelo

Resultados medidos no ambiente local, úteis se alguém questionar a fidelidade ao paper.

### A.1 — A velocidade penalizada segue a fórmula ERMAC

`speed_penalizado = round(speed_default / (1 + h/Q))`, com `Q = 10`. Conferência sobre os
hotspots reais (`GET /hotspots`):

| h | v_default (km/h) | v_penalizado (km/h) | fórmula | confere? |
|---:|---:|---:|---:|:---:|
| 32 | 50 | 12 | 12 | ✅ |
| 30 | 30 | 8 | 8 | ✅ |
| 26 | 49 | 14 | 14 | ✅ |
| 24 | 49 | 14 | 14 | ✅ |
| 20 | 40 | 13 | 13 | ✅ |
| 18 | 40 | 14 | 14 | ✅ |
| 17 | 50 | 19 | 19 | ✅ |
| 16 | 50 | 19 | 19 | ✅ |

Total: **879 arestas** afetadas, `max_h = 32`.

### A.2 — A penalidade é isolada às vias com histórico

Uma rota inteiramente fora dos hotspots tem o **mesmo** tempo no seco e na chuva — ou seja,
o switch chuva/seco **não** penaliza ruas sem histórico (não é um simples "trânsito de dia"):

```
rota sem hotspots:   seco 1,100 km / 110,7 s   |   chuva 1,100 km / 110,7 s   |   Δt = 0,0 s
```

### A.3 — A penalidade aparece na via com histórico

Rota curta cruzando o pior hotspot (`h = 32`):

```
seco  (free_flow):   0,239 km / 26,4 s
chuva (constrained): 0,239 km / 53,3 s
>> penalidade efetiva: +102% no tempo (mesma distância)
```

---

## Apêndice B — Como o switch chuva/seco funciona (resumo técnico)

O Valhalla não tem um flag de "chuva". O switch é feito pelo **horário em `date_time`**
(ver [07 — Quirks](07-quirks-e-decisoes.md), Quirk #1):

- `date_time` noturno (03:00) → Valhalla usa `free_flow_speed` = velocidade original → **modo seco**
- `date_time` diurno (13:00) → Valhalla usa `constrained_speed` = velocidade penalizada → **modo chuva**

O backend recebe `chuva: bool` e gera o `date_time` correto. As velocidades penalizadas dos
879 hotspots estão gravadas nos tiles (coluna `constrained_speed`); as demais arestas não foram
tocadas, por isso A.2 dá Δt = 0.

---

## Apêndice C — (Re)script dos dados fictícios

Os dados fictícios da Demo 1 ficam no PostGIS. Se o banco for limpo, recrie-os com o
script [`scripts/seed_demo_alagamentos.py`](../scripts/seed_demo_alagamentos.py) — roda dentro
do container `backend` (tem Python + acesso ao Valhalla e ao Nominatim):

```powershell
docker exec -i backend python - < scripts\seed_demo_alagamentos.py
# -> snapshot publicado: {"inseridos": 8, ...}
```

O script:
1. calcula a rota base Casa Verde → República,
2. acha os 2 pontos que bloqueiam a travessia do Tietê (maior desvio),
3. geocoda alguns pontos extras pela cidade (marcadores visuais),
4. publica o snapshot via `POST /alagamentos/snapshot` (idêntico ao scraper).

### Limpar os dados fictícios (deixar o mapa limpo)

```powershell
curl -X POST http://localhost:8000/alagamentos/snapshot -H "Content-Type: application/json" -d "{\"pontos\":[]}"
```

Isso marca todos os ativos como resolvidos e não insere nada — o mapa volta a 0 alagamentos.
(O scraper do CGE, diferente deste POST direto, **aborta** com lista vazia para não limpar o
banco por engano — ver [05 — Pipeline](05-pipeline-trafego.md).)
