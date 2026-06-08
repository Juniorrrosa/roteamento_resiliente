# 01 — Visão geral

## O problema

São Paulo registra, em média, dezenas de pontos de alagamento durante eventos de chuva forte. Esses pontos:

- **Bloqueiam ruas em tempo real** — equipes de emergência precisam contornar
- **Têm padrão recorrente** — algumas vias historicamente alagam mais que outras (alguns trechos têm dezenas de registros em 10 anos)

Um motor de roteamento "genérico" (Google Maps, Waze) só leva em conta trânsito atual. Não considera o risco de chegar e encontrar a via bloqueada por água.

## A proposta

Combinar duas fontes de dados num único motor de roteamento:

| Fonte | Origem | Papel no modelo |
|---|---|---|
| **Alagamentos em tempo real** | CGE-SP (web scraping) | Restrição **dura** — rota não pode passar |
| **Histórico de alagamento** | Shapefile `Alag-Inun_2015-2025.shp` (CONDICAO=INTRANSITAVEL, 2015–2025) | Restrição **suave** — rota prefere evitar, mas pode usar se necessário |

Resultado: rotas que evitam pontos atualmente alagados **e** dão preferência a vias com menor histórico de alagamento — quando está chovendo.

## O paper de referência

**"Resilient routing during flood"**
Gislaine Camila de Freitas, Leonardo Bacelar Lima Santos, Tiago Rodrigues Macedo
Universidade Federal de São Paulo (UNIFESP) + Centro Nacional de Monitoramento e Alertas de Desastres Naturais (Cemaden)
Encontro de Matemática Aplicada e Computacional — ERMAC 2026

Disponível em `modelo_py/ERMAC_2026_Gislaine_novomodelo.pdf`.

**Fórmula central:**

$$
w(e) = b(e) \cdot \left(1 + \frac{h(e)}{Q}\right) \cdot l(e)
$$

- `b(e)` ∈ {1, ∞}: 1 se aresta não alagada agora, ∞ se alagada
- `h(e)`: nº de vezes que a aresta foi bloqueada por alagamento no histórico
- `l(e)`: comprimento físico da aresta (m)
- `Q`: fator de calibração (sensibilidade ao histórico). Default: `Q = 10.0`

O custo total de um caminho é a soma dos `w(e)` das arestas. Algoritmo: A*.

Ver detalhes da implementação em [03 — Modelo matemático](03-modelo-matematico.md).

## Contexto de uso

- **Cobertura geográfica:** região metropolitana de São Paulo (recorte RMSP — capital + conurbação: Guarulhos, Osasco, ABC, etc.). Histórico de alagamento e dados do CGE cobrem a cidade de SP — fora dessa região o roteamento opera sem penalidade histórica (cai em Dijkstra padrão).
- **Modo de operação atual:** scraper CGE em modo **batch** (manual). A versão de produção futura terá polling automático — ver [09 — Roadmap](09-roadmap.md).
- **Quem usa:** equipes de emergência, defesa civil, motoristas durante eventos de chuva. Cidadão acessa via frontend (a construir).

## O que NÃO é objetivo

- Não é um sistema de previsão de alagamento — só usa eventos confirmados (RT do CGE) e histórico.
- Não usa machine learning para inferir risco — é uma fórmula explícita parametrizada por `Q`.
- Não substitui Waze/Google Maps para uso geral — é específico para o cenário de chuva em SP.
