import { useEffect, useState } from "react";
import MapView from "./components/MapView.jsx";
import RouteForm from "./components/RouteForm.jsx";
import RoutesPanel from "./components/RoutesPanel.jsx";
import { getAlagamentos, getHotspots, postRota } from "./api.js";
import { toApiLocation } from "./lib/format.js";
import { MARKER } from "./lib/colors.js";
import { SCENARIOS } from "./lib/scenarios.js";

const TODAS_VISIVEIS = Object.fromEntries(SCENARIOS.map((s) => [s.key, true]));
const SEM_ROTAS = Object.fromEntries(SCENARIOS.map((s) => [s.key, null]));

export default function App() {
  const [origem, setOrigem] = useState(null);
  const [destino, setDestino] = useState(null);

  const [rotas, setRotas] = useState(SEM_ROTAS);
  const [visiveis, setVisiveis] = useState(TODAS_VISIVEIS);

  const [alagamentos, setAlagamentos] = useState([]);
  const [hotspots, setHotspots] = useState({ pontos: [], max_h: 0 });
  const [showHotspots, setShowHotspots] = useState(false);

  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState(null);
  const [flyTarget, setFlyTarget] = useState(null);
  const [panelOpen, setPanelOpen] = useState(true);

  useEffect(() => {
    getAlagamentos().then(setAlagamentos).catch((e) => console.error("alagamentos:", e.message));
    getHotspots().then(setHotspots).catch((e) => console.error("hotspots:", e.message));
  }, []);

  // --- pontos ---
  function onMapClick(coords) {
    const pt = { source: "mapa", lat: coords[0], lng: coords[1] };
    if (!origem) setOrigem(pt);
    else if (!destino) setDestino(pt);
    else {
      setOrigem(pt);
      setDestino(null);
    }
  }

  function onGps() {
    if (!navigator.geolocation) {
      setErro("Geolocalização não suportada neste navegador.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = [pos.coords.latitude, pos.coords.longitude];
        setOrigem({ source: "gps", lat: coords[0], lng: coords[1] });
        setFlyTarget(coords);
      },
      (err) => setErro(`Não foi possível obter sua localização (${err.message}).`),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function onToggle(key) {
    setVisiveis((v) => ({ ...v, [key]: !v[key] }));
  }

  function onLimpar() {
    setOrigem(null);
    setDestino(null);
    setRotas(SEM_ROTAS);
    setVisiveis(TODAS_VISIVEIS);
    setErro(null);
  }

  // --- cálculo: as 4 condições em paralelo ---
  async function onCalcular() {
    const o = toApiLocation(origem);
    const d = toApiLocation(destino);
    if (!o || !d) {
      setErro("Defina origem e destino (endereço, clique no mapa ou GPS).");
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      // allSettled: uma rota que falha (ex.: cenário sem caminho) não derruba as demais.
      const settled = await Promise.allSettled(
        SCENARIOS.map((s) =>
          postRota({
            origem: o,
            destino: d,
            chuva: s.chuva,
            evitar_alagamentos: s.evitar,
            alternates: 0,
          })
        )
      );
      const novo = { ...SEM_ROTAS };
      let okCount = 0;
      let ultimoErro = null;
      SCENARIOS.forEach((s, i) => {
        const r = settled[i];
        if (r.status === "fulfilled") {
          novo[s.key] = r.value;
          okCount += 1;
        } else {
          ultimoErro = r.reason;
        }
      });
      if (okCount === 0) throw ultimoErro || new Error("Falha ao calcular rotas.");
      setRotas(novo);
      setVisiveis(TODAS_VISIVEIS);
    } catch (e) {
      setErro(e.message);
      setRotas(SEM_ROTAS);
    } finally {
      setLoading(false);
    }
  }

  const temResultado = Object.values(rotas).some(Boolean);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>Roteamento Resiliente <span className="brand-sub">· São Paulo</span></h1>
        </div>
        <button className="panel-toggle" onClick={() => setPanelOpen((v) => !v)} aria-label="Mostrar/ocultar painel">
          {panelOpen ? "✕" : "☰"}
        </button>
      </header>

      <div className="layout">
        <aside className={`sidebar ${panelOpen ? "open" : "closed"}`}>
          <RouteForm
            origem={origem}
            destino={destino}
            onOrigemEndereco={(s) => setOrigem(s ? { source: "endereco", endereco: s } : null)}
            onDestinoEndereco={(s) => setDestino(s ? { source: "endereco", endereco: s } : null)}
            onClearOrigem={() => setOrigem(null)}
            onClearDestino={() => setDestino(null)}
            onGps={onGps}
            onCalcular={onCalcular}
            onLimpar={onLimpar}
            temAlgo={Boolean(origem || destino || temResultado)}
            loading={loading}
          />

          {erro && <div className="error">⚠️ {erro}</div>}

          {temResultado && <RoutesPanel rotas={rotas} visiveis={visiveis} onToggle={onToggle} />}

          <div className="layers">
            <label className="toggle">
              <input type="checkbox" checked={showHotspots} onChange={(e) => setShowHotspots(e.target.checked)} />
              <span>Histórico de alagamentos ({hotspots.pontos.length})</span>
            </label>
          </div>

          <div className="legend">
            <div><span className="lg lg-dot" style={{ background: MARKER.alagamento }} /> alagamento ativo (CGE)</div>
            <div><span className="lg lg-dot" style={{ background: "#f59f00" }} /> hotspot histórico (severidade)</div>
            <div><span className="lg lg-dot" style={{ background: MARKER.origem }} /> origem · <span className="lg lg-dot" style={{ background: MARKER.destino }} /> destino</div>
          </div>

          <p className="hint">{alagamentos.length} alagamento(s) ativo(s) agora (CGE).</p>
        </aside>

        <main className="map-wrap">
          {loading && (
            <div className="map-loading">
              <div className="spinner" />
              <span>Calculando rotas…</span>
            </div>
          )}
          <MapView
            rotas={rotas}
            visiveis={visiveis}
            alagamentos={alagamentos}
            hotspots={hotspots.pontos}
            maxH={hotspots.max_h}
            showHotspots={showHotspots}
            origem={origem}
            destino={destino}
            flyTarget={flyTarget}
            onMapClick={onMapClick}
          />
        </main>
      </div>
    </div>
  );
}
