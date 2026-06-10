# Frontend — Roteamento Resiliente

Interface web (MVP) para calcular rotas que evitam alagamentos em São Paulo.

## Stack

- **React 18 + Vite**
- **react-leaflet / Leaflet** (mapa, tiles OpenStreetMap)
- **@mapbox/polyline** para decodificar o `shape` das rotas

> ⚠️ O Valhalla codifica o `shape` com **precisão 6** (não a 5 padrão). Decodificamos com `polyline.decode(shape, 6)` em [`src/lib/polyline.js`](src/lib/polyline.js) — precisão errada distorce a rota no mapa.

## Como o front fala com o backend

Todas as chamadas vão para `/api/*`, que é proxiado para o backend FastAPI:

- **Em dev** (`npm run dev`): o proxy do Vite encaminha `/api` → `http://localhost:8000` (ver `vite.config.js`).
- **Em produção** (container): o nginx encaminha `/api/` → `http://backend:8000/` (ver `nginx.conf`).

Assim o navegador só fala com o frontend — sem CORS.

## Rodar

### Via Docker (recomendado, junto com a stack)

```powershell
cd runtime
docker compose up -d            # sobe backend + frontend + valhalla + postgis
# interface em http://localhost:3000
```

### Dev local (hot reload)

Precisa de Node 20+. O backend precisa estar rodando em `localhost:8000`.

```powershell
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

## Funcionalidades

- Busca por **endereço** (origem/destino) ou inserção por **clique no mapa** (1º origem, 2º destino, 3º reinicia) ou **GPS** (botão "Minha localização")
- **4 rotas por condição climática/ambiental** (combinações de chuva × alagamento), cada uma em uma cor:
  | cor | chuva | evita alagamento |
  |---|---|---|
  | 🟢 verde | não | não (ideal) |
  | 🔵 azul | sim | não |
  | 🟠 laranja | não | sim |
  | 🔴 vermelho | sim | sim (pior caso) |
  - A **legenda é o controle de visibilidade**: clicar liga/desliga cada rota no mapa
  - Cada item mostra **distância, tempo** e nº de alagamentos evitados
  - Sobreposições legíveis via **espessuras concêntricas** (pior por baixo → ideal por cima)
- Camada de **hotspots históricos** (pesos estáticos) com toggle, círculos coloridos por severidade `h(e)`
- Marcadores de **alagamentos do CGE** em tempo real

## Endpoints consumidos

| Chamada | Endpoint backend | Uso |
|---|---|---|
| `getAlagamentos()` | `GET /alagamentos` | marcadores vermelhos (CGE tempo real) |
| `getHotspots()` | `GET /hotspots` | camada de severidade histórica |
| `postRota()` | `POST /rota` | chamado 4× (1 por cenário) com `chuva`/`evitar_alagamentos` e `alternates: 0` |

## Estrutura

```
src/
├── main.jsx, App.jsx          # bootstrap + orquestração de estado
├── api.js                     # cliente HTTP (/api)
├── lib/
│   ├── polyline.js            # decode precisão 6
│   ├── format.js              # km/min/coord + toApiLocation
│   ├── colors.js              # cores de marcadores + rampa de hotspots
│   └── scenarios.js           # os 4 cenários (chuva × alagamento): cor, espessura, flags
├── components/
│   ├── MapView.jsx            # mapa, clique, GPS flyTo, 4 rotas concêntricas, hotspots (canvas)
│   ├── PointInput.jsx         # campo de ponto (endereço OU chip de mapa/GPS)
│   ├── RouteForm.jsx          # origem/destino + GPS + botão
│   └── RoutesPanel.jsx        # legenda-controle das 4 rotas (toggle + métricas)
└── styles.css
```

## Fora do MVP (ver `docs/09-roadmap.md`)

Heatmap contínuo (hoje os hotspots são círculos por severidade), reverse-geocoding dos pontos por clique/GPS, cache de estado (TanStack Query).
