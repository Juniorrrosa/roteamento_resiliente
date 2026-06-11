// Cores dos marcadores e da rampa de hotspots.
// As cores das 4 rotas ficam em scenarios.js.

// Origem (verde) e destino (roxo) — mesmas cores dos pinos no mapa (ver lib/icons.js).
export const MARKER = {
  origem: "#2f9e44",
  destino: "#7048e8",
  alagamento: "#e03131",
};

// Rampa de severidade dos hotspots históricos (h baixo -> alto).
export function hotspotColor(h, maxH) {
  const t = maxH > 0 ? Math.min(1, h / maxH) : 0;
  const stops = [
    [252, 196, 25], // amarelo
    [245, 159, 0],
    [232, 89, 12],
    [201, 42, 42], // vermelho escuro
  ];
  const seg = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(seg));
  const f = seg - i;
  const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}
