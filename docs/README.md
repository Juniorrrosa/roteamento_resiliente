# Documentação — Roteamento Resiliente

Sistema de roteamento urbano para São Paulo que combina dados históricos de alagamento (peso) com dados em tempo real (bloqueio), conforme o modelo matemático do paper **ERMAC 2026 — "Resilient routing during flood"** (Freitas, Santos, Macedo — UNIFESP/Cemaden).

Esta pasta contém a documentação operacional e técnica do projeto. Comece pelo índice abaixo conforme seu interesse.

## Para quem está começando

1. [01 — Visão geral](01-visao-geral.md) — o que o projeto resolve, paper de referência
2. [02 — Arquitetura](02-arquitetura.md) — componentes e fluxo de dados
3. [03 — Modelo matemático](03-modelo-matematico.md) — fórmula e como ela mapeia no Valhalla, com evidências empíricas

## Para operação no dia a dia

4. [04 — Infraestrutura](04-infraestrutura.md) — Docker Compose, como subir/parar, variáveis de ambiente
5. [05 — Pipeline de tráfego](05-pipeline-trafego.md) — quando e como rodar `refresh_traffic.py`, troubleshooting
6. [06 — API do Valhalla](06-api-valhalla.md) — exemplos de request, parâmetros, alternativas

## Para entender as decisões tomadas

7. [07 — Quirks e decisões](07-quirks-e-decisoes.md) — gotchas descobertos, dívidas técnicas conhecidas

## Para deploy e roadmap

8. [08 — Deploy](08-deploy.md) — secrets, backups, considerações de produção
9. [09 — Roadmap](09-roadmap.md) — o que já está pronto (Etapas 0–5: infra, pipeline, backend, scraper, frontend) e o que falta (polling, monitoramento, deploy)

## Para apresentar / demonstrar

- [demo — roteiro de apresentação](demo.md) — passo a passo no frontend para mostrar as duas componentes do modelo (restrição dura com alagamento RT + restrição suave com peso histórico), com números medidos e evidências de validação

> Cada componente tem seu próprio README: [`backend/`](../backend/README.md), [`frontend/`](../frontend/README.md), [`scraper/`](../scraper/README.md).

---

## Quick start (TL;DR)

Pré-requisitos: Docker Desktop em execução, Python 3.11+, ~5 GB de disco livre.

```powershell
# 1. subir a infra (Valhalla + PostGIS + Backend + Frontend)
cd runtime
Copy-Item .env.example .env       # edite a senha se for ambiente compartilhado
docker compose up -d

# 2. preparar venv do pipeline ERMAC
cd ..
python -m venv scripts\.venv
.\scripts\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt

# 3. gerar e injetar pesos historicos (h(e) -> velocidade penalizada)
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py

# 4. (opcional) geocoder Nominatim + coletar alagamentos do CGE
docker compose --profile geocoding up -d nominatim
docker compose --profile scraper run --rm scraper run --once
```

Pronto: **interface web em `http://localhost:3000`**, API em `http://localhost:8000`, motor de rota em `http://localhost:8002`. Para testar o motor direto:

```powershell
curl -X POST http://localhost:8002/route -H "Content-Type: application/json" `
  -d '{\"locations\":[{\"lat\":-23.5695,\"lon\":-46.6080},{\"lat\":-23.5675,\"lon\":-46.6078}],\"costing\":\"auto\",\"date_time\":{\"type\":1,\"value\":\"2026-05-18T13:00\"}}'
```

> **Convenção dos exemplos:** `date_time` com hora **noturna** (~03:00) = modo seco (sem penalidade); hora **diurna** (~13:00) = modo chuva (com penalidade). Veja [07 — Quirks](07-quirks-e-decisoes.md) para entender o porquê.
