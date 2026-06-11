// Bases de mapa disponíveis. `thumb` é um tile real de São Paulo (z=11) no
// próprio estilo — serve de preview no seletor de miniaturas.
const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const CARTO_ATTR = `${OSM_ATTR} &copy; <a href="https://carto.com/attributions">CARTO</a>`;
const ESRI_ATTR = "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics";

// Tile que cobre o centro de SP no zoom 11 (x=758, y=1161).
export const BASEMAPS = [
  {
    id: "osm",
    name: "Mapa",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: OSM_ATTR,
    thumb: "https://a.tile.openstreetmap.org/11/758/1161.png",
  },
  {
    id: "claro",
    name: "Claro",
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    attribution: CARTO_ATTR,
    thumb: "https://a.basemaps.cartocdn.com/light_all/11/758/1161.png",
  },
  {
    id: "escuro",
    name: "Escuro",
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    attribution: CARTO_ATTR,
    thumb: "https://a.basemaps.cartocdn.com/dark_all/11/758/1161.png",
  },
  {
    id: "satelite",
    name: "Satélite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
    thumb: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/11/1161/758",
  },
];
