// Geração de KML (Keyhole Markup Language) a partir de uma rota.
// O KML resultante abre no Google Earth, Google Maps (importar), QGIS, etc.

import { decodeShape } from "./polyline.js";

// Converte cor hex "#rrggbb" para o formato KML "aabbggrr" (alpha, blue, green, red).
function hexToKmlColor(hex, alpha = "ff") {
  const h = (hex || "#1971c2").replace("#", "");
  const rr = h.slice(0, 2);
  const gg = h.slice(2, 4);
  const bb = h.slice(4, 6);
  return `${alpha}${bb}${gg}${rr}`;
}

// Escapa caracteres especiais de XML em texto livre (nomes, descrições).
function xmlEscape(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pointPlacemark(name, [lat, lng]) {
  return `    <Placemark>
      <name>${xmlEscape(name)}</name>
      <Point><coordinates>${lng},${lat},0</coordinates></Point>
    </Placemark>`;
}

/**
 * Monta uma string KML válida para uma rota.
 *
 * @param {object} opts
 * @param {string} opts.name           Nome do documento/rota
 * @param {string} [opts.description]   Descrição livre (distância, tempo, etc.)
 * @param {string} opts.shape          Polyline codificada (precisão 6) do Valhalla
 * @param {[number,number]} [opts.origem]   [lat, lng]
 * @param {[number,number]} [opts.destino]  [lat, lng]
 * @param {string} [opts.colorHex]      Cor da linha em "#rrggbb"
 * @returns {string} KML
 */
export function buildRouteKml({ name, description, shape, origem, destino, colorHex }) {
  const coords = decodeShape(shape); // [[lat, lng], ...]
  const lineCoords = coords.map(([lat, lng]) => `${lng},${lat},0`).join(" ");
  const lineColor = hexToKmlColor(colorHex);

  const placemarks = [];
  if (origem) placemarks.push(pointPlacemark("Origem", origem));
  if (destino) placemarks.push(pointPlacemark("Destino", destino));

  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${xmlEscape(name)}</name>
    <description>${xmlEscape(description || "")}</description>
    <Style id="rotaResiliente">
      <LineStyle><color>${lineColor}</color><width>5</width></LineStyle>
    </Style>
${placemarks.join("\n")}
    <Placemark>
      <name>${xmlEscape(name)}</name>
      <styleUrl>#rotaResiliente</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>${lineCoords}</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>`;
}
