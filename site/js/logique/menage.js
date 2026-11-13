/**
 * From the engine's correspondences (one per written name) to the cards of the results page
 * (one per notice): the rows of one household — principal, spouse, children — are shown on one
 * card, with the matched persons marked. Pure functions.
 */

export const CLASSES = Object.freeze(['correspondance', 'graphie-approchante', 'partielle']);

/**
 * @param {Object[]} correspondances engine results, already in display order; each carries
 *        "cle" (the key of its card: "an:<principal row>" or "bogga:<row>") and "ligne"
 * @returns {Object<string, {cle: string, classe: string, touches: Object[]}[]>} cards per class.
 *          A card sits in the class of its best correspondence (the first met, since the engine
 *          sorts by class first); "touches" lists every matched row of the card, best first.
 */
export function grouperParNotice(correspondances) {
  const parClasse = { correspondance: [], 'graphie-approchante': [], partielle: [] };
  const cartes = new Map();
  for (const c of Array.isArray(correspondances) ? correspondances : []) {
    if (!c || typeof c.cle !== 'string' || !(c.classe in parClasse)) continue;
    let carte = cartes.get(c.cle);
    if (carte === undefined) {
      carte = { cle: c.cle, classe: c.classe, touches: [] };
      cartes.set(c.cle, carte);
      parClasse[c.classe].push(carte);
    }
    // One row may match once per class at most; keep its best (first) correspondence.
    if (!carte.touches.some((t) => t.ligne === c.ligne)) carte.touches.push(c);
  }
  return parClasse;
}

/** Cards shown at first in each class, and how many each "Afficher plus" adds. */
export const PAS = 10;
/** Cards kept in the page at any time, all classes together. */
export const BUDGET = 50;

/**
 * Sliding windows over the cards of each class, so that the page never holds more than
 * BUDGET cards: asking for more in one class first takes room from the START of that same
 * class (those cards are replaced by a "revenir au début" line).
 *
 * @param {Object<string, number>} totaux  cards available per class
 * @param {Object<string, {debut: number, fin: number}>} [fenetres] current windows
 * @param {{classe: string, action: 'plus'|'debut'}} [demande]
 * @param {{pas?: number, budget?: number}} [options]
 * @returns {Object<string, {debut: number, fin: number}>}
 */
export function fenetresDeCartes(totaux, fenetres, demande, { pas = PAS, budget = BUDGET } = {}) {
  const out = {};
  for (const cls of CLASSES) {
    const total = Math.max(0, totaux?.[cls] ?? 0);
    const w = fenetres?.[cls];
    const fin = Math.min(total, w ? w.fin : pas);
    const debut = Math.min(Math.max(0, w ? w.debut : 0), fin);
    out[cls] = { debut, fin };
  }
  if (demande && CLASSES.includes(demande.classe)) {
    const w = out[demande.classe];
    const total = Math.max(0, totaux?.[demande.classe] ?? 0);
    if (demande.action === 'debut') {
      const size = Math.min(pas, total);
      w.debut = 0;
      w.fin = size;
    } else {
      w.fin = Math.min(total, w.fin + pas);
      const others = CLASSES.filter((c) => c !== demande.classe).reduce((sum, c) => sum + (out[c].fin - out[c].debut), 0);
      const room = Math.max(pas, budget - others);
      if (w.fin - w.debut > room) w.debut = w.fin - room;
    }
  }
  return out;
}

/**
 * Split a written name around the words that matched, for highlighting.
 * @param {string} nom       the name exactly as written
 * @param {string[]} ecrits  the written words reported by the engine ("ecrit" of each term)
 * @returns {{texte: string, touche: boolean}[]} pieces whose concatenation is exactly "nom"
 */
export function surligner(nom, ecrits) {
  const text = String(nom ?? '');
  const spans = [];
  for (const word of [...new Set(ecrits ?? [])].filter((w) => typeof w === 'string' && w !== '').sort((a, b) => b.length - a.length)) {
    let from = 0;
    for (;;) {
      const at = text.indexOf(word, from);
      if (at < 0) break;
      const end = at + word.length;
      const before = at === 0 ? '' : text[at - 1];
      const after = end >= text.length ? '' : text[end];
      const free = !spans.some((s) => at < s[1] && end > s[0]);
      if (free && !/\p{L}/u.test(before) && !/\p{L}/u.test(after)) {
        spans.push([at, end]);
        break;
      }
      from = at + 1;
    }
  }
  spans.sort((a, b) => a[0] - b[0]);
  const pieces = [];
  let cursor = 0;
  for (const [at, end] of spans) {
    if (at > cursor) pieces.push({ texte: text.slice(cursor, at), touche: false });
    pieces.push({ texte: text.slice(at, end), touche: true });
    cursor = end;
  }
  if (cursor < text.length) pieces.push({ texte: text.slice(cursor), touche: false });
  return pieces;
}
