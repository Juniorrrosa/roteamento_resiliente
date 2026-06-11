import PointInput from "./PointInput.jsx";

const COR_ORIGEM = "#2f9e44";
const COR_DESTINO = "#6741d9";

export default function RouteForm({
  origem,
  destino,
  onOrigemEndereco,
  onDestinoEndereco,
  onClearOrigem,
  onClearDestino,
  onGps,
  onCalcular,
  onLimpar,
  temAlgo,
  loading,
}) {
  const podeCalcular = Boolean(origem) && Boolean(destino) && !loading;

  function handleSubmit(e) {
    e.preventDefault();
    if (podeCalcular) onCalcular();
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <PointInput
        label="Origem"
        icon={COR_ORIGEM}
        point={origem}
        placeholder="Endereço ou clique no mapa"
        onChangeEndereco={onOrigemEndereco}
        onClear={onClearOrigem}
      />

      <PointInput
        label="Destino"
        icon={COR_DESTINO}
        point={destino}
        placeholder="Endereço ou clique no mapa"
        onChangeEndereco={onDestinoEndereco}
        onClear={onClearDestino}
      />

      <div className="form-actions">
        <button type="button" className="btn-ghost" onClick={onGps} title="Usar minha localização">
          📍 Minha localização
        </button>
        <button type="button" className="btn-ghost" onClick={onLimpar} disabled={!temAlgo} title="Limpar tudo">
          🗑️ Limpar
        </button>
      </div>

      <p className="hint hint-inline">
        Dica: clique no mapa para marcar <b>origem</b> e depois <b>destino</b>.
      </p>

      <button type="submit" className="btn" disabled={!podeCalcular}>
        {loading ? "Calculando…" : "Calcular rota"}
      </button>
    </form>
  );
}
