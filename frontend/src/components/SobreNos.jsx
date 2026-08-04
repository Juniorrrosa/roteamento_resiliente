import gislaine from "../assets/team/gislaine.jpeg";
import gabriel from "../assets/team/gabriel.jpeg";
import satolo from "../assets/team/satolo.jpeg";
import tiago from "../assets/team/tiago.jpeg";
import leduino from "../assets/team/leduino.jpeg";
import leonardo from "../assets/team/leonardo.jpeg";
import junior from "../assets/team/junior.jpeg";

import logoiFAST from "../assets/institutions/logoiFAST.png";
import logoCNPq from "../assets/institutions/logoCNPq.png";
import logoFAPESP from "../assets/institutions/logoFAPESP.png";
import logoCemaden from "../assets/institutions/logoCemaden.png";
import logoUnifesp from "../assets/institutions/logoUnifesp.png";

const COLABORADORES = [
  {
    nome: "Gislaine Freitas",
    foto: gislaine,
    bio: "Doutoranda no Programa de Pós-Graduação em Ciência da Computação da Universidade Federal de São Paulo (UNIFESP). Mestre em Pesquisa Operacional pelo Instituto Tecnológico de Aeronáutica (ITA) e pela Universidade Federal de São Paulo (UNIFESP) e especialista em Business Intelligence pela Universidade Anhembi Morumbi (UAM).",
  },
  {
    nome: "Junior Rosa",
    foto: junior,
    bio: "Engenheiro da computação formado pela Universidade do Vale do Paraíba (UNIVAP) e candidato ao mestrado em Computação Aplicada pelo Instituto Nacional de Pesquisas Espaciais (INPE).",
  },
  {
    nome: "Leonardo Santos",
    foto: leonardo,
    bio: "Pesquisador Titular em Modelagem Computacional no CEMADEN-MCTI e professor em programas de pós-graduação do Instituto Nacional de Pesquisas Espaciais (INPE) e da Universidade Federal de São Paulo (UNIFESP). Doutor pelo Instituto Nacional de Pesquisas Espaciais (INPE), com formação em Física pela Universidade Federal da Bahia (UFBA), atuou também como professor visitante na Universidade Humboldt de Berlim (HU Berlin).",
  },
  {
    nome: "Gabriel Silva Delgado",
    foto: gabriel,
    bio: "Professor no Instituto Federal do Espírito Santo (IFES) – Campus de Alegre. Graduado em Lic. Matemática pelo Instituto Federal de São Paulo (IFSP), Mestrado Profissional PROFMAT pela Universidade Federal de São Paulo (UNIFESP) e doutorando no PPG-PO em uma parceria entre a Universidade Federal de São Paulo (UNIFESP) e o Instituto Tecnológico de Aeronáutica (ITA). Atua com otimização não linear atrelado a regiões de confiança.",
  },
  {
    nome: "Luiz Fernando Satolo",
    foto: satolo,
    bio: "Professor do Instituto Tecnológico de Aeronáutica (ITA). Mestre em Computação Aplicada pelo Instituto Nacional de Pesquisas Espaciais (INPE) e Doutor em Economia Aplicada pela Universidade de São Paulo (USP), foi bolsista DTI-A CNPq do projeto iFAST no CEMADEN. Atua nas áreas de Métodos Quantitativos de Apoio à Decisão e Ciências de Dados Geoespaciais.",
  },
  {
    nome: "Tiago Macedo",
    foto: tiago,
    bio: "Professor associado do Instituto de Ciência e Tecnologia da Universidade Federal de São Paulo (UNIFESP). Doutor em Matemática pela Universidade Estadual de Campinas (UNICAMP), foi pesquisador visitante também na University of Georgia (Estados Unidos) e na University of Ottawa (Canadá).",
  },
  {
    nome: "Luiz Leduino Salles Neto",
    foto: leduino,
    bio: "Professor Titular do Instituto de Ciência e Tecnologia da Universidade Federal de São Paulo (UNIFESP) e atual Presidente do Escritório de Integridade Acadêmica da universidade. Foi pesquisador visitante na University of Colorado Denver (Estados Unidos) e na Universidad de Sevilla (Espanha). Atua nas áreas de Matemática Aplicada e de Pesquisa Operacional, com ênfase em aplicações à logística e a sistemas inteligentes de apoio à decisão.",
  },
];

// `size` = altura em px de cada logo. Alguns PNGs têm mais margem interna e
// parecem menores; ajustamos individualmente para equilibrar o visual.
const INSTITUICOES = [
  { nome: "iFAST", logo: logoiFAST, url: "https://sites.google.com/view/projectifast", size: 34 },
  { nome: "CNPq", logo: logoCNPq, url: "https://www.gov.br/cnpq/pt-br", size: 34 },
  { nome: "FAPESP", logo: logoFAPESP, url: "https://fapesp.br/", size: 46 },
  { nome: "CEMADEN", logo: logoCemaden, url: "https://www.gov.br/cemaden/pt-br", size: 46 },
  { nome: "UNIFESP", logo: logoUnifesp, url: "https://www.unifesp.br/", size: 46 },
];

// Seção "Sobre nós" no rodapé da barra lateral (área de fundo branco).
export default function SobreNos() {
  return (
    <section className="about">
      <h2>Sobre nós</h2>

      <p className="about-tech">
        Sistema de roteamento resiliente a alagamentos construído inteiramente com
        ferramentas <strong>livres e de código aberto</strong>. As rotas são calculadas pelo
        motor <strong>Valhalla</strong> sobre a malha viária do <strong>OpenStreetMap</strong>,
        com geocodificação por endereço via <strong>Nominatim</strong>. O back-end é uma API em{" "}
        <strong>FastAPI (Python)</strong> apoiada em <strong>PostgreSQL/PostGIS</strong>, e a
        interface é feita em <strong>React + Vite</strong> com mapas <strong>Leaflet</strong>. Os
        alagamentos em tempo real vêm dos dados públicos do <strong>CGE-SP</strong>, e toda a
        infraestrutura roda em contêineres <strong>Docker</strong>.
      </p>

      <h3 className="about-sub">Colaboradores</h3>
      <ul className="collab-list">
        {COLABORADORES.map((c) => (
          <li key={c.nome} className="collab-card">
            <img className="collab-photo" src={c.foto} alt={`Foto de ${c.nome}`} loading="lazy" />
            <div className="collab-body">
              <span className="collab-name">{c.nome}</span>
              <span className="collab-bio">{c.bio}</span>
            </div>
          </li>
        ))}
      </ul>

      <h3 className="about-sub">Apoio</h3>
      <div className="inst-logos">
        {INSTITUICOES.map((i) => (
          <a
            key={i.nome}
            className="inst-logo-link"
            href={i.url}
            target="_blank"
            rel="noopener noreferrer"
            title={i.nome}
          >
            <img
              className="inst-logo"
              src={i.logo}
              alt={`Logo ${i.nome}`}
              loading="lazy"
              style={{ height: `${i.size}px` }}
            />
          </a>
        ))}
      </div>
    </section>
  );
}
