/**
 * Where the reader was on a page, kept in that page's own history entry (history.state), so
 * that the browser's "back" brings them back to the same place: the scroll position, the cards
 * that were open, the link they followed, and what the view itself wants to remember (how many
 * cards of each class were shown). Pure functions: app.js reads and writes history.state.
 *
 * history.state stays in this tab: it is never sent anywhere. It is still read as untrusted
 * input (another script of the same page could have written it), so every field is checked.
 */

export const CLE_POSITION = 'decretas';

const MAX_OUVERTS = 200;
const MAX_TEXTE = 300;

const texteCourt = (v) => typeof v === 'string' && v.length > 0 && v.length <= MAX_TEXTE;

/**
 * @param {*} state  history.state
 * @returns {{y: number, ouverts: string[], cible: {cle: string, href: string|null}|null, vue: Object}|null}
 */
export function lirePosition(state) {
  const s = state && typeof state === 'object' ? state[CLE_POSITION] : null;
  if (!s || typeof s !== 'object') return null;
  const y = Number.isFinite(s.y) && s.y >= 0 && s.y < 1e7 ? Math.round(s.y) : 0;
  const ouverts = Array.isArray(s.ouverts) ? s.ouverts.filter(texteCourt).slice(0, MAX_OUVERTS) : [];
  const cible = s.cible && typeof s.cible === 'object' && texteCourt(s.cible.cle)
    ? { cle: s.cible.cle, href: texteCourt(s.cible.href) ? s.cible.href : null }
    : null;
  const vue = s.vue && typeof s.vue === 'object' && !Array.isArray(s.vue) ? s.vue : {};
  return { y, ouverts, cible, vue };
}

/**
 * A new history.state with the position updated; the other keys of the state are kept.
 * @param {*} state  current history.state
 * @param {{y?: number, ouverts?: string[], cible?: Object|null, vue?: Object}} patch
 */
export function avecPosition(state, patch) {
  const base = state && typeof state === 'object' && !Array.isArray(state) ? state : {};
  const avant = lirePosition(base) ?? { y: 0, ouverts: [], cible: null, vue: {} };
  const apres = { ...avant, ...patch, vue: { ...avant.vue, ...(patch.vue ?? {}) } };
  return { ...base, [CLE_POSITION]: apres };
}

/**
 * The card windows a results page saved, if they still fit the classes and the counts.
 * @param {*} sauvees  position.vue.fenetres
 * @param {Object<string, number>} totaux cards per class now
 * @returns {Object<string, {debut: number, fin: number}>|null}
 */
export function fenetresSauvees(sauvees, totaux) {
  if (!sauvees || typeof sauvees !== 'object') return null;
  const out = {};
  for (const [classe, total] of Object.entries(totaux ?? {})) {
    const w = sauvees[classe];
    if (!w || !Number.isInteger(w.debut) || !Number.isInteger(w.fin) || w.debut < 0 || w.fin < w.debut || w.fin > total) return null;
    out[classe] = { debut: w.debut, fin: w.fin };
  }
  return out;
}
