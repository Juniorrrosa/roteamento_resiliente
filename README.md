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

    Deve-se criar essa pasta 'data' na raiz do projeto contendo o arquivo OpenStreetMap (.pbf). Nesse projeto é utilizado o `sao-paulo.osm.pbf` — um recorte da **região metropolitana de São Paulo** (bbox `-47.05,-24.05,-46.15,-23.25`).
    
    - sao-paulo.osm.pbf
        
        Esse arquivo é a malha da localidade que o Valhalla utiliza. Cobre a capital + conurbação (Guarulhos, Osasco, ABC, etc.). Após rodar o build, são criadas automaticamente as pastas tiles, valhalla e valhalla.json.
        
        O Geofabrik só fatia o Brasil em macrorregiões (Sudeste, Sul, ...), sem recorte estadual/municipal. Para gerar o recorte de SP, baixe o `sudeste-latest.osm.pbf` de [download.geofabrik.de](https://download.geofabrik.de/south-america/brazil.html) e recorte com o `osmium`:
        
        ```powershell
        cd data
        docker run --rm -v ${PWD}:/data stefda/osmium-tool `
          osmium extract -b -47.05,-24.05,-46.15,-23.25 --strategy smart `
          /data/sudeste-latest.osm.pbf -o /data/sao-paulo.osm.pbf
        ```
        
        > Para mudar a área de cobertura, ajuste a bbox acima (ou use outra região do Geofabrik), regenere o `.pbf` e rode o build novamente apontando pro arquivo no `docker-compose.build.yml`. Após o rebuild, reinjete os pesos com `python scripts/refresh_traffic.py --force-backup`.
        >
> 📖 **Documentação completa em [`docs/`](docs/README.md)** — visão geral, arquitetura, evidências da fidelidade ao paper, infraestrutura, pipeline, API, decisões técnicas e roadmap.

## Quick start

```powershell
# 1. infra base (Valhalla + PostGIS + Backend FastAPI + Frontend)
cd runtime
Copy-Item .env.example .env       # edite a senha
docker compose up -d

# 2. preparar venv do pipeline ERMAC
cd ..
python -m venv scripts\.venv
.\scripts\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt

# 3. injetar pesos historicos (h(e) -> velocidade penalizada nos tiles)
.\scripts\.venv\Scripts\python.exe scripts\refresh_traffic.py

# 4. (opcional) geocoder Nominatim e scraper do CGE
docker compose --profile geocoding up -d nominatim   # 1a vez: import ~3 min
docker compose --profile scraper run --rm scraper run --once
```

Após esses passos: **interface web em `http://localhost:3000`**, API em `http://localhost:8000` (`/health`, `/rota`, ...), motor de rota em `http://localhost:8002`. Exemplos de request em [docs/06-api-valhalla.md](docs/06-api-valhalla.md).

## Estrutura do projeto

| Pasta | Conteúdo |
|---|---|
| `docs/` | Documentação operacional e técnica — **comece por aqui** |
| `build/` | `docker-compose.build.yml` para gerar tiles do Valhalla a partir do `.pbf` (rodado uma vez) |
| `runtime/` | `docker-compose.yml` da infra rodando (Valhalla + PostGIS + Nominatim) |
| `data/` | `.pbf` OSM, tiles do Valhalla, CSVs de tráfego, relatórios. **Não commitado.** |
| `modelo_py/` | Shapefile histórico + protótipo Python original do paper |
| `scripts/` | Pipeline ERMAC → Valhalla (`build_traffic_csvs.py`, `refresh_traffic.py`) |
| `backend/` | ✅ Backend FastAPI (`/rota`, `/alagamentos`, `/geocode`, `/health`) |
| `scraper/` | ✅ Scraper CGE-SP (Selenium + Nominatim + push snapshot) |
| `frontend/` | ✅ Frontend React + Vite + Leaflet (nginx, proxy `/api`) |
| `infra/` | (a fazer) Configuração de deploy / IaC |

## Referências

- Paper: `modelo_py/ERMAC_2026_Gislaine_novomodelo.pdf`
- Tiles OSM: <https://download.geofabrik.de/south-america/brazil.html>
- Scraper CGE-SP original: <https://github.com/vitor-yuichi/cge_scrapper>

## Licença

MIT — ver [LICENSE](LICENSE).

