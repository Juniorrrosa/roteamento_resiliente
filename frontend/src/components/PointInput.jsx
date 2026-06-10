import { fmtCoord } from "../lib/format.js";

// Campo de um ponto (origem ou destino). Dois modos:
//  - endereço: input de texto normal
//  - mapa/GPS: chip com a coordenada e um ✕ para limpar
export default function PointInput({ label, icon, point, placeholder, onChangeEndereco, onClear }) {
  const fromCoords = point && point.lat != null && point.source !== "endereco";

  return (
    <label className="field">
      <span className="field-label">
        <span className="field-dot" style={{ background: icon }} />
        {label}
      </span>

      {fromCoords ? (
        <div className="chip">
          <span className="chip-text">
            {point.source === "gps" ? "📍 Minha localização" : "📌 Ponto no mapa"}
            <small>{fmtCoord(point.lat, point.lng)}</small>
          </span>
          <button type="button" className="chip-x" onClick={onClear} aria-label="limpar">
            ✕
          </button>
        </div>
      ) : (
        <input
          type="text"
          value={point?.endereco ?? ""}
          onChange={(e) => onChangeEndereco(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
        />
      )}
    </label>
  );
}
