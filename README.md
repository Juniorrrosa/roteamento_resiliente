# Roteamento Resiliente

Sistema de roteamento urbano para São Paulo que evita pontos de alagamento em tempo real e pondera por histórico de alagamento, conforme o modelo matemático do paper **ERMAC 2026 — "Resilient routing during flood"** (UNIFESP/Cemaden).

- build
    - docker-compose.build.yml
        
        Esse arquivo é rodado uma unica vez. Justamente para carregar todos os tiles e configurações iniciais do valhalla.
        
        Para rodar use `docker-compose -f docker-compose.build.yml up`
        
- runtime
    - docker-compose.yml
        
        Esse arquivo é rodado para iniciar o container do valhalla. Rodando toda vez que queremos iniciar o container.
        
        Para rodar use `docker-compose up`
        
- data

    Deve-se criar essa pasta 'data' na raiz do projeto contendo o arquivo OpenStreetMap (.pbf). Nesse projeto foi utilizado o `sudeste-latest.osm.pbf`
    
    - sudeste-latest.osm.pbf
        
        Esse arquivo é a malha da localidade que queremos utilizar o valhalla. Sendo representada somente pela região sudeste nesse projeto. Após rodar o build deverá criar automaticamente as pastas tiles, valhalla e valhalla.json
        
        Para baixar demais localidades, visite: [https://download.geofabrik.de/](https://download.geofabrik.de/south-america/brazil.html) 
        
        > Sempre que baixar uma nova localidade, Rode o build novamente com a região desejada dentro da pasta ‘data’ e aponte devidamente no arquivo `docker-compose.build.yml`
        >
> 📖 **Documentação completa em [`docs/`](docs/README.md)** — visão geral, arquitetura, evidências da fidelidade ao paper, infraestrutura, pipeline, API, decisões técnicas e roadmap.

## Quick start

```powershell
# 1. infra base (Valhalla + PostGIS)
cd runtime
Copy-Item .env.example .env       # edite a senha
docker compose up -d

# 2. preparar venv do pipeline ERMAC
cd ..
python -m venv scripts\.venv
.\scripts\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt

# 3. injetar pesos historicos (h(e) -> velocidade penalizada nos tiles)
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py
```

Após esses passos, o motor de rota está em `http://localhost:8002`. Exemplo de request em [docs/06-api-valhalla.md](docs/06-api-valhalla.md).

## Estrutura do projeto

| Pasta | Conteúdo |
|---|---|
| `docs/` | Documentação operacional e técnica — **comece por aqui** |
| `build/` | `docker-compose.build.yml` para gerar tiles do Valhalla a partir do `.pbf` (rodado uma vez) |
| `runtime/` | `docker-compose.yml` da infra rodando (Valhalla + PostGIS + Nominatim) |
| `data/` | `.pbf` OSM, tiles do Valhalla, CSVs de tráfego, relatórios. **Não commitado.** |
| `modelo_py/` | Shapefile histórico + protótipo Python original do paper |
| `scripts/` | Pipeline ERMAC → Valhalla (`build_traffic_csvs.py`, `refresh_traffic.py`) |
| `backend/` | (a fazer) Backend FastAPI |
| `frontend/` | (a fazer) Frontend React + Leaflet |
| `scraper/` | (a fazer) Scraper CGE-SP adaptado |
| `infra/` | (a fazer) Configuração de deploy / IaC |

## Referências

- Paper: `modelo_py/ERMAC_2026_Gislaine_novomodelo.pdf`
- Tiles OSM: <https://download.geofabrik.de/south-america/brazil.html>
- Scraper CGE-SP original: <https://github.com/vitor-yuichi/cge_scrapper>

## Licença

MIT — ver [LICENSE](LICENSE).

