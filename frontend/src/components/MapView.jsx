import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { decodeShape } from "../lib/polyline.js";
import { MARKER, hotspotColor } from "../lib/colors.js";
import { DRAW_ORDER } from "../lib/scenarios.js";

const SP_CENTER = [-23.5505, -46.6333];

function ClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, 15, { duration: 0.8 });
  }, [target, map]);
  return null;
}

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points && points.length > 1) {
      map.fitBounds(points, { padding: [50, 50], maxZoom: 16 });
    }
  }, [points, map]);
  return null;
}

export default function MapView({
  rotas,
  visiveis,
  alagamentos,
  hotspots,
  maxH,
  showHotspots,
  origem,
  destino,
  flyTarget,
  onMapClick,
}) {
  // Camadas das rotas: mais grossas por baixo (DRAW_ORDER), só as visíveis.
  const layers = DRAW_ORDER.filter((s) => visiveis[s.key] && rotas[s.key]?.rotas?.[0]).map((s) => ({
    key: s.key,
    coords: decodeShape(rotas[s.key].rotas[0].shape),
    color: s.color,
    weight: s.weight,
  }));

  // Coords de origem/destino: do ponto (clique/GPS) ou do que o backend resolveu.
  const algumResultado = Object.values(rotas).find(Boolean);
  const origemPt =
    origem?.lat != null ? [origem.lat, origem.lng] : algumResultado?.origem_usada ?? null;
  const destinoPt =
    destino?.lat != null ? [destino.lat, destino.lng] : algumResultado?.destino_usado ?? null;

  const fitPoints = layers.flatMap((l) => l.coords);

  return (
    <MapContainer center={SP_CENTER} zoom={12} className="map" preferCanvas>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <ClickHandler onMapClick={onMapClick} />
      <FlyTo target={flyTarget} />
      {fitPoints.length > 1 && <FitBounds points={fitPoints} />}

      {/* Hotspots históricos (pesos estáticos) */}
      {showHotspots &&
        hotspots.map((hp, i) => (
          <CircleMarker
            key={`hs-${i}`}
            center={[hp.lat, hp.lng]}
            radius={4 + (maxH ? (hp.h / maxH) * 7 : 0)}
            pathOptions={{ stroke: false, fillColor: hotspotColor(hp.h, maxH), fillOpacity: 0.6 }}
          >
            <Tooltip>
              <strong>Histórico</strong>
              <br />
              {hp.h} ocorrência(s) · {hp.speed_default}→{hp.speed_penalizado} km/h
            </Tooltip>
          </CircleMarker>
        ))}

      {/* As 4 rotas (concêntricas) */}
      {layers.map((l) => (
        <Polyline
          key={l.key}
          positions={l.coords}
          pathOptions={{ color: l.color, weight: l.weight, opacity: 0.9, lineCap: "round" }}
        />
      ))}

      {/* Alagamentos do CGE (tempo real) */}
      {alagamentos.map((a) => (
        <CircleMarker
          key={`al-${a.id}`}
          center={[a.lat, a.lng]}
          radius={7}
          pathOptions={{ color: "#fff", weight: 1.5, fillColor: MARKER.alagamento, fillOpacity: 0.95 }}
        >
          <Tooltip>
            <strong>Alagamento ativo (CGE)</strong>
            <br />
            {a.endereco_raw || a.bairro || "ponto CGE"}
            {a.sentido ? (
              <>
                <br />
                <em>{a.sentido}</em>
              </>
            ) : null}
          </Tooltip>
        </CircleMarker>
      ))}

      {/* Origem / destino (neutros, para não confundir com as cores das rotas) */}
      {origemPt && (
        <CircleMarker center={origemPt} radius={9}
          pathOptions={{ color: "#fff", weight: 3, fillColor: MARKER.origem, fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Origem</Tooltip>
        </CircleMarker>
      )}
      {destinoPt && (
        <CircleMarker center={destinoPt} radius={9}
          pathOptions={{ color: "#fff", weight: 3, fillColor: MARKER.destino, fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Destino</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
