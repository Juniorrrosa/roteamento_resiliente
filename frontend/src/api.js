// Cliente HTTP do backend. Todas as chamadas passam por /api, que e proxiado
// para o backend FastAPI (Vite proxy em dev, nginx no container).

const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* corpo nao-JSON: mantem o status */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

/** GET /health — status agregado dos servicos. */
export function getHealth() {
  return request("/health");
}

/** GET /alagamentos — pontos ativos do CGE (tempo real). */
export function getAlagamentos() {
  return request("/alagamentos");
}

/** GET /hotspots — hotspots historicos (pesos estaticos do modelo). */
export function getHotspots() {
  return request("/hotspots");
}

/**
 * POST /rota — calcula rota(s) entre origem e destino.
 * @param {{origem: object, destino: object, chuva: boolean, evitar_alagamentos?: boolean, alternates?: number}} payload
 */
export function postRota({ origem, destino, chuva, evitar_alagamentos = true, alternates = 2 }) {
  return request("/rota", {
    method: "POST",
    body: JSON.stringify({ origem, destino, chuva, evitar_alagamentos, alternates }),
  });
}
