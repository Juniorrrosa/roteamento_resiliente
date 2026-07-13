import { useEffect, useRef, useState } from "react";
import { buildRouteKml } from "../lib/kml.js";
import { buildRouteGpx } from "../lib/gpx.js";
import { decodeShape } from "../lib/polyline.js";
import { gmapsDirUrl, sampleWaypoints } from "../lib/maps.js";
import { downloadGpx, downloadKml, openEmail, openWhatsApp, slugify } from "../lib/share.js";
import { fmtKm, fmtMin } from "../lib/format.js";

// Botão "Exportar / compartilhar" de uma rota: abre um menu com baixar .kml,
// abrir no Google Maps, WhatsApp e e-mail.
export default function RouteExport({ scenario, res, principal }) {
  const [open, setOpen] = useState(false);
  const [aviso, setAviso] = useState(null);
  const boxRef = useRef(null);

  // fecha o popover ao clicar fora
  useEffect(() => {
    if (!open) return;
    function onDoc(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const origem = res?.origem_usada;
  const destino = res?.destino_usado;
  const baseName = `rota-${slugify(scenario.short)}`;
  const titulo = `Rota resiliente — ${scenario.label}`;
  const descricao = `${fmtKm(principal.length_km)} · ${fmtMin(principal.time_seconds)}`;

  // URL do Google Maps com waypoints amostrados do traçado da rota.
  const waypoints = sampleWaypoints(decodeShape(principal.shape), 8);
  const mapsUrl = gmapsDirUrl(origem, destino, waypoints);

  function gerarKml() {
    return buildRouteKml({
      name: titulo,
      description: descricao,
      shape: principal.shape,
      origem,
      destino,
      colorHex: scenario.color,
    });
  }

  function gerarGpx() {
    return buildRouteGpx({
      name: titulo,
      description: descricao,
      shape: principal.shape,
      origem,
      destino,
    });
  }

  function mensagem() {
    const linhas = [`🗺️ ${titulo}`, `📏 ${descricao}`];
    const gmaps = gmapsDirUrl(origem, destino);
    if (gmaps) linhas.push(`🔗 Abrir no mapa: ${gmaps}`);
    return linhas.join("\n");
  }

  function flash(msg) {
    setAviso(msg);
    setTimeout(() => setAviso(null), 3500);
  }

  function handleBaixarKml() {
    downloadKml(`${baseName}.kml`, gerarKml());
    setOpen(false);
  }

  function handleBaixarGpx() {
    downloadGpx(`${baseName}.gpx`, gerarGpx());
    setOpen(false);
  }

  // WhatsApp/e-mail não aceitam anexo via link: baixamos o .kml e abrimos o app
  // com a mensagem (resumo + link do mapa) para o usuário anexar o arquivo.
  function handleWhatsApp() {
    downloadKml(`${baseName}.kml`, gerarKml());
    openWhatsApp(`${mensagem()}\n\n(arquivo .kml da rota baixado para anexar)`);
    flash("KML baixado — anexe-o no WhatsApp.");
    setOpen(false);
  }

  function handleEmail() {
    downloadKml(`${baseName}.kml`, gerarKml());
    openEmail(titulo, `${mensagem()}\n\n(arquivo .kml da rota baixado para anexar)`);
    flash("KML baixado — anexe-o no e-mail.");
    setOpen(false);
  }

  return (
    <div className="scn-actions" ref={boxRef}>
      <button
        type="button"
        className="scn-act-btn"
        onClick={() => setOpen((v) => !v)}
        title="Exportar / compartilhar esta rota"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        ⤴
      </button>

      {open && (
        <div className="scn-export-menu" role="menu">
          <button type="button" role="menuitem" onClick={handleBaixarKml}>
            📥 Baixar .kml
          </button>
          <button type="button" role="menuitem" onClick={handleBaixarGpx}>
            📥 Baixar .gpx
          </button>
          {mapsUrl && (
            <a
              role="menuitem"
              href={mapsUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setOpen(false)}
            >
              🗺️ Abrir no Google Maps
            </a>
          )}
          <button type="button" role="menuitem" onClick={handleWhatsApp}>
            🟢 WhatsApp
          </button>
          <button type="button" role="menuitem" onClick={handleEmail}>
            ✉️ E-mail
          </button>
        </div>
      )}

      {aviso && <span className="scn-export-aviso">{aviso}</span>}
    </div>
  );
}
