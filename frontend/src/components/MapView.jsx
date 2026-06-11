import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Marker,
  Tooltip,
  ScaleControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { decodeShape } from "../lib/polyline.js";
import { MARKER, hotspotColor } from "../lib/colors.js";
import { DRAW_ORDER } from "../lib/scenarios.js";
import { PIN_ORIGEM, PIN_DESTINO } from "../lib/icons.js";
import { BASEMAPS } from "../lib/basemaps.js";
import BaseMapSwitcher from "./BaseMapSwitcher.jsx";

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
  const [baseId, setBaseId] = useState("osm");

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
  const base = BASEMAPS.find((b) => b.id === baseId) ?? BASEMAPS[0];

  return (
    <div className="map-shell">
      <MapContainer center={SP_CENTER} zoom={12} className="map" preferCanvas>
        <TileLayer key={base.id} attribution={base.attribution} url={base.url} />

        <ScaleControl position="bottomleft" imperial={false} />

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

      {/* Origem (pino verde) / destino (pino roxo) */}
      {origemPt && (
        <Marker position={origemPt} icon={PIN_ORIGEM}>
          <Tooltip direction="top">Origem</Tooltip>
        </Marker>
      )}
      {destinoPt && (
        <Marker position={destinoPt} icon={PIN_DESTINO}>
          <Tooltip direction="top">Destino</Tooltip>
        </Marker>
      )}
      </MapContainer>

      <BaseMapSwitcher value={baseId} onChange={setBaseId} />
    </div>
  );
}
