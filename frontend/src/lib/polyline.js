import polyline from "@mapbox/polyline";

// IMPORTANTE: o Valhalla codifica o shape com precisao 6 (1e-6), nao a precisao 5
// padrao do Google. Decodificar com a precisao errada deixa a rota distorcida.
// polyline.decode retorna [[lat, lng], ...] — formato que o Leaflet espera.
export function decodeShape(shape) {
  if (!shape) return [];
  return polyline.decode(shape, 6);
}
