// Geração de GPX (GPS Exchange Format) a partir de uma rota.
// O GPX carrega a geometria completa como <trk> e é seguível com turn-by-turn
// fiel em apps como OsmAnd, Organic Maps e Garmin.

import { decodeShape } from "./polyline.js";

function xmlEscape(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function wpt(name, [lat, lng]) {
  return `  <wpt lat="${lat}" lon="${lng}"><name>${xmlEscape(name)}</name></wpt>`;
}

/**
 * Monta uma string GPX 1.1 válida para uma rota.
 *
 * @param {object} opts
 * @param {string} opts.name           Nome da rota/track
 * @param {string} [opts.description]   Descrição livre (distância, tempo, etc.)
 * @param {string} opts.shape          Polyline codificada (precisão 6) do Valhalla
 * @param {[number,number]} [opts.origem]   [lat, lng]
 * @param {[number,number]} [opts.destino]  [lat, lng]
 * @returns {string} GPX
 */
export function buildRouteGpx({ name, description, shape, origem, destino }) {
  const coords = decodeShape(shape); // [[lat, lng], ...]
  const trkpts = coords
    .map(([lat, lng]) => `      <trkpt lat="${lat}" lon="${lng}"></trkpt>`)
    .join("\n");

  const waypoints = [];
  if (origem) waypoints.push(wpt("Origem", origem));
  if (destino) waypoints.push(wpt("Destino", destino));

  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Roteamento Resiliente" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${xmlEscape(name)}</name>
    <desc>${xmlEscape(description || "")}</desc>
  </metadata>
${waypoints.join("\n")}
  <trk>
    <name>${xmlEscape(name)}</name>
    <trkseg>
${trkpts}
    </trkseg>
  </trk>
</gpx>`;
}
