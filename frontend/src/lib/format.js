// Formatação de métricas para exibição (pt-BR).

export function fmtKm(km) {
  return `${km.toFixed(1).replace(".", ",")} km`;
}

export function fmtMin(seconds) {
  const min = Math.round(seconds / 60);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${h}h${String(m).padStart(2, "0")}`;
}

export function fmtCoord(lat, lng) {
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

// Converte o ponto interno (endereço OU coords) no formato que o POST /rota espera.
export function toApiLocation(point) {
  if (!point) return null;
  if (point.lat != null && point.lng != null) {
    return { lat: point.lat, lng: point.lng };
  }
  if (point.endereco) return { endereco: point.endereco };
  return null;
}
