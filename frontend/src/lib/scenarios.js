// As 4 condições climáticas/ambientais = combinações de (chuva) × (evitar alagamento).
// `weight` cresce do ideal (fina, por cima) ao pior (grossa, por baixo) para que
// trechos sobrepostos apareçam como faixas concêntricas.

export const SCENARIOS = [
  {
    key: "ideal",
    label: "Sem chuva, sem alagamento",
    short: "Ideal",
    chuva: false,
    evitar: false,
    color: "#2f9e44",
    weight: 4,
  },
  {
    key: "chuva",
    label: "Com chuva, sem alagamento",
    short: "Chuva",
    chuva: true,
    evitar: false,
    color: "#1971c2",
    weight: 5.5,
  },
  {
    key: "alagamento",
    label: "Sem chuva, com alagamento",
    short: "Alagamento",
    chuva: false,
    evitar: true,
    color: "#f08c00",
    weight: 7,
  },
  {
    key: "pior",
    label: "Com chuva e alagamento",
    short: "Pior caso",
    chuva: true,
    evitar: true,
    color: "#e03131",
    weight: 9,
  },
];

// Ordem de desenho no mapa: mais grossas por baixo, finas por cima.
export const DRAW_ORDER = [...SCENARIOS].sort((a, b) => b.weight - a.weight);
