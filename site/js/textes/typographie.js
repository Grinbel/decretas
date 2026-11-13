/**
 * French typography for the sentences of the interface and of the content files: a no-break
 * space inside « guillemets » and before : ; ? ! — so that a line never starts with « : » or
 * ends with « « » — and a narrow no-break space inside a number (« 6 000 »). Applied to OUR
 * sentences only (textes/*.js, site/contenu/*.json, our labels of the meta files); what is
 * copied from a source (a name, a title of decree, a raw line) is never touched.
 */

const NBSP = ' ';
const NNBSP = ' '; // narrow no-break space, the French thousands separator

/** @param {string} texte @returns {string} */
export function typographier(texte) {
  return String(texte)
    .replace(/« /g, `«${NBSP}`)
    .replace(/ »/g, `${NBSP}»`)
    .replace(/ ([:;?!])(?=\s|$|[»)])/g, `${NBSP}$1`)
    // « 6 000 », « 52 427 »: never split across two lines (a group of exactly three digits)
    .replace(/(\d) (?=\d{3}(?!\d))/g, `$1${NNBSP}`);
}

/**
 * Deep copy of a tree of strings, arrays, objects and functions, with every string — and every
 * string returned by a function — passed through typographier(). Other values are kept.
 * @param {*} valeur
 * @param {(cle: string, valeur: *) => boolean} [sauf] values copied as they are (addresses,
 *        ids): called with the key and its value, so that a key naming a list of identifiers
 *        can be told apart from the same key holding sentences (« guides » of guides.json)
 */
export function typographierTout(valeur, sauf = () => false) {
  if (typeof valeur === 'string') return typographier(valeur);
  if (typeof valeur === 'function') {
    return (...args) => {
      const out = valeur(...args);
      return typeof out === 'string' ? typographier(out) : out;
    };
  }
  if (Array.isArray(valeur)) return valeur.map((v) => typographierTout(v, sauf));
  if (valeur !== null && typeof valeur === 'object') {
    return Object.fromEntries(Object.entries(valeur).map(([k, v]) => [k, sauf(k, v) ? v : typographierTout(v, sauf)]));
  }
  return valeur;
}

/**
 * The "sauf" of the content files: a technical key is copied as it is only when it holds an
 * identifier, an address, or a list of them; when it holds objects — the « guides », « types »
 * or « liens » of a file are whole guides, cards and links — their sentences are typographed,
 * and their own technical keys are kept as they are, one level down.
 * @param {Set<string>} techniques
 * @returns {(cle: string, valeur: *) => boolean}
 */
export function saufTechniques(techniques) {
  const simple = (x) => x === null || typeof x !== 'object';
  return (cle, valeur) => techniques.has(cle) && (simple(valeur) || (Array.isArray(valeur) && valeur.every(simple)));
}
