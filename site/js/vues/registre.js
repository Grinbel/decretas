/**
 * The view registry: the seam between the shell (app.js) and the pages.
 *
 * A view is an object:
 *   {
 *     titre(route, contexte)            -> string, the document title (without the site name)
 *     monter(conteneur, route, contexte) -> void | (() => void)   build the page into the <main>
 *                                          element; may return a clean-up function
 *     actualiser?(route, contexte)      -> boolean  optional: called instead of a re-mount when
 *                                          only the parameters changed; return false to re-mount
 *   }
 * and is registered under the first segment of its address:
 *   enregistrer('guides', vueGuides)    ->  #/guides, #/guides/<id>
 *
 * "contexte" is built once by app.js: { donnees, contenu, aller, T } (see js/README.md).
 */

const vues = new Map();

/** @param {string} nom first segment of the address ('' is the home page) */
export function enregistrer(nom, vue) {
  if (typeof vue?.monter !== 'function' || typeof vue?.titre !== 'function') {
    throw new TypeError(`View "${nom}": titre() and monter() are required.`);
  }
  vues.set(nom, vue);
}

export function trouver(nom) {
  return vues.get(nom) ?? null;
}

export function nomsDesVues() {
  return [...vues.keys()];
}
