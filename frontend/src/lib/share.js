// Helpers de exportação/compartilhamento por texto: download do .kml, WhatsApp e e-mail.
// (Links como wa.me/mailto não anexam arquivo — por isso baixamos o .kml e abrimos o app
//  com uma mensagem de resumo para o usuário anexar.)

const MIME_KML = "application/vnd.google-earth.kml+xml";
const MIME_GPX = "application/gpx+xml";

// Transforma um texto em nome de arquivo seguro: "Pior caso" -> "pior-caso".
export function slugify(s) {
  return String(s)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // remove diacríticos (é -> e)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

// Dispara o download de um conteúdo de texto como arquivo no navegador.
export function downloadText(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // libera o object URL no próximo tick (alguns navegadores precisam dele durante o click)
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadKml(filename, kml) {
  downloadText(filename, kml, MIME_KML);
}

export function downloadGpx(filename, gpx) {
  downloadText(filename, gpx, MIME_GPX);
}

// Abre o WhatsApp (app ou web) com uma mensagem pré-preenchida.
export function openWhatsApp(text) {
  window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
}

// Abre o cliente de e-mail com assunto e corpo pré-preenchidos.
export function openEmail(subject, body) {
  window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
