/**
 * A tiny hash router. The whole state of a page lives after the "#" of the address, which a
 * browser never sends to a server: a search can be bookmarked and shared without being
 * transmitted to the site that hosts these files.
 *
 *   #/                         -> { nom: '',          segments: [],      params: {} }
 *   #/recherche?q=…&ne=1876    -> { nom: 'recherche', segments: [],      params: {q: '…', ne: '1876'} }
 *   #/guides/legifrance-jorf   -> { nom: 'guides',    segments: ['legifrance-jorf'], params: {} }
 */

/**
 * @param {string} hash  location.hash ("#/recherche?q=a") or anything else
 * @returns {{nom: string, segments: string[], params: Object<string, string>}}
 */
export function analyserHash(hash) {
  let rest = String(hash ?? '');
  // Only "#/…" is a route. Anything else ("", "#", an in-page anchor) is the home page.
  if (!rest.startsWith('#/')) return { nom: '', segments: [], params: {} };
  rest = rest.slice(2);
  const cut = rest.indexOf('?');
  const path = cut < 0 ? rest : rest.slice(0, cut);
  const query = cut < 0 ? '' : rest.slice(cut + 1);
  const decode = (part) => {
    try {
      return decodeURIComponent(part);
    } catch (error) {
      if (error instanceof URIError) return part;
      throw error;
    }
  };
  const parts = path.split('/').filter((p) => p !== '').map(decode);
  const params = {};
  for (const [key, value] of new URLSearchParams(query)) if (!(key in params)) params[key] = value;
  return { nom: parts[0] ?? '', segments: parts.slice(1), params };
}

/**
 * @param {string} nom                 view name ('' for the home page)
 * @param {string[]} [segments]
 * @param {Object<string, string|number|null|undefined>} [params] empty values are left out
 * @returns {string} "#/…"
 */
export function formerHash(nom, segments = [], params = {}) {
  const path = [nom, ...segments].filter((p) => p !== '' && p !== null && p !== undefined).map((p) => encodeURIComponent(String(p))).join('/');
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== null && value !== undefined && String(value) !== '') query.set(key, String(value));
  }
  const q = query.toString();
  return `#/${path}${q === '' ? '' : `?${q}`}`;
}

/**
 * Bind the router to the window.
 * @param {Object} options
 * @param {(route: Object) => void} options.surRoute  called at start and at every change of hash
 * @returns {{aller: (hash: string, o?: {remplacer?: boolean}) => void, route: () => Object}}
 */
export function demarrerRouteur({ surRoute }) {
  const route = () => analyserHash(window.location.hash);
  window.addEventListener('hashchange', () => surRoute(route()));
  surRoute(route());
  return {
    route,
    /** Go to a hash. "remplacer": do not add an entry to the history (refinements of a search). */
    aller(hash, { remplacer = false } = {}) {
      if (hash === window.location.hash) {
        surRoute(route());
      } else if (remplacer) {
        window.history.replaceState(null, '', hash);
        surRoute(route());
      } else {
        window.location.hash = hash;
      }
    },
  };
}
