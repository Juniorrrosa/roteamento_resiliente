// Helpers para montar URLs de direções do Google Maps a partir de uma rota.

// Link de direções no Google Maps. `waypoints` (opcional) é uma lista de [lat, lng]
// intermediários para forçar o Maps a seguir aproximadamente o nosso traçado.
export function gmapsDirUrl(origem, destino, waypoints = []) {
  if (!origem || !destino) return null;
  const o = `${origem[0]},${origem[1]}`;
  const d = `${destino[0]},${destino[1]}`;
  let url = `https://www.google.com/maps/dir/?api=1&origin=${o}&destination=${d}&travelmode=driving`;
  if (waypoints && waypoints.length) {
    const wp = waypoints.map(([lat, lng]) => `${lat},${lng}`).join("|");
    url += `&waypoints=${encodeURIComponent(wp)}`;
  }
  return url;
}

// Amostra até `max` pontos interiores (exclui extremos) uniformemente espaçados.
// Usado para reduzir o shape da rota (centenas de pontos) ao limite do Google Maps.
export function sampleWaypoints(coords, max = 8) {
  if (!coords || coords.length <= 2) return [];
  const interior = coords.slice(1, -1);
  if (interior.length <= max) return interior;
  const step = (interior.length - 1) / (max - 1);
  const out = [];
  for (let i = 0; i < max; i++) out.push(interior[Math.round(i * step)]);
  return out;
}
