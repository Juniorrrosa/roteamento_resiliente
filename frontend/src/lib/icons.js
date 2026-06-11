import L from "leaflet";

// Pino em formato de gota (SVG inline via divIcon) — sem depender de imagens,
// então não esbarra no bug clássico do ícone padrão quebrado do Leaflet em bundlers.
// A ponta do pino fica no `iconAnchor` (base central), apontando a coordenada exata.
function pinSvg(color) {
  return `
    <svg width="30" height="42" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.4 0 0 5.4 0 12c0 8.9 12 22 12 22s12-13.1 12-22C24 5.4 18.6 0 12 0z"
            fill="${color}" stroke="#ffffff" stroke-width="2"/>
      <circle cx="12" cy="12" r="4.6" fill="#ffffff"/>
    </svg>`;
}

export function makePin(color) {
  return L.divIcon({
    html: pinSvg(color),
    className: "pin-icon",
    iconSize: [30, 42],
    iconAnchor: [15, 42],
    popupAnchor: [0, -38],
    tooltipAnchor: [0, -34],
  });
}

export const PIN_ORIGEM = makePin("#2f9e44"); // verde
export const PIN_DESTINO = makePin("#7048e8"); // roxo
