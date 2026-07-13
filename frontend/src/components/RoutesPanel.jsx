import { SCENARIOS } from "../lib/scenarios.js";
import { fmtKm, fmtMin } from "../lib/format.js";
import RouteExport from "./RouteExport.jsx";

// Legenda + controle de visibilidade das 4 rotas. Clicar na linha liga/desliga.
export default function RoutesPanel({ rotas, visiveis, onToggle }) {
  return (
    <div className="result">
      <h2>Rotas por condição</h2>
      <p className="hint hint-inline">Clique para mostrar/ocultar cada rota no mapa.</p>

      <ul className="scenarios">
        {SCENARIOS.map((s) => {
          const res = rotas[s.key];
          const principal = res?.rotas?.[0];
          const on = visiveis[s.key];
          return (
            <li key={s.key} className="scn-item">
              <button
                type="button"
                className={`scn ${on ? "" : "off"}`}
                onClick={() => onToggle(s.key)}
                aria-pressed={on}
              >
                <span className="scn-line" style={{ background: s.color, opacity: on ? 1 : 0.3 }} />
                <span className="scn-body">
                  <span className="scn-label">{s.label}</span>
                  <span className={`scn-metrics ${res?.bloqueada ? "scn-blocked" : ""}`}>
                    {principal
                      ? `${fmtKm(principal.length_km)} · ${fmtMin(principal.time_seconds)}`
                      : res?.bloqueada
                        ? "🚧 sem rota livre de alagamento"
                        : "—"}
                  </span>
                </span>
                <span className="scn-eye">{on ? "👁️" : "🚫"}</span>
              </button>
              {principal && <RouteExport scenario={s} res={res} principal={principal} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
