import { useState } from "react";
import { BASEMAPS } from "../lib/basemaps.js";

// Seletor de mapa base com miniaturas (preview real do estilo).
// Colapsado: mostra só a base atual. Ao abrir: galeria das 4 opções.
export default function BaseMapSwitcher({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const atual = BASEMAPS.find((b) => b.id === value) ?? BASEMAPS[0];

  if (!open) {
    return (
      <div className="basemaps">
        <button
          className="bm-thumb bm-current"
          style={{ backgroundImage: `url(${atual.thumb})` }}
          onClick={() => setOpen(true)}
          title="Trocar mapa base"
        >
          <span className="bm-label">▦ {atual.name}</span>
        </button>
      </div>
    );
  }

  return (
    <div className="basemaps open" onMouseLeave={() => setOpen(false)}>
      {BASEMAPS.map((b) => (
        <button
          key={b.id}
          className={`bm-thumb ${b.id === value ? "active" : ""}`}
          style={{ backgroundImage: `url(${b.thumb})` }}
          onClick={() => {
            onChange(b.id);
            setOpen(false);
          }}
          title={b.name}
        >
          <span className="bm-label">{b.name}</span>
        </button>
      ))}
    </div>
  );
}
