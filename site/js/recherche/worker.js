/**
 * Search Web Worker: a thin wrapper around session.js (which documents the message protocol:
 * charger / chercher / suggerer / etat, and the progression / pret / correspondances / erreur replies).
 *
 * Start it as a module worker, from the page:
 *   const worker = new Worker('js/recherche/worker.js', { type: 'module' });
 *   worker.onmessage = (event) => { … event.data.type … };
 *   worker.postMessage({ type: 'charger', fichiers: [
 *     { url: 'data/an-personnes.json', groupe: 'an' },
 *     { url: 'data/bogga-entrees.json', groupe: 'bogga', ocr: true } ] });
 *
 * Relative data URLs: inside a worker, a relative URL is resolved by the browser against the
 * WORKER SCRIPT (…/js/recherche/worker.js), not against the page — 'data/an-personnes.json'
 * would be asked for under js/recherche/ and answer 404. This wrapper therefore resolves them
 * against the site root, two levels above this file, so that the call above works as written
 * from a page at the root of the site. A page elsewhere gives its own base:
 *   worker.postMessage({ type: 'charger', base: document.baseURI, fichiers: […] });
 *
 * The only network access is the download of the data files named in "charger", from the
 * site itself. A query is never sent anywhere.
 */

import { createSession } from './session.js';

/** Root of the site: this file is <root>/js/recherche/worker.js. Null outside a browser. */
const SITE_ROOT = typeof self.location === 'object' && self.location !== null && typeof self.location.href === 'string'
  ? new URL('../../', self.location.href).href
  : null;

const session = createSession({
  post: (message) => self.postMessage(message),
  fetch: (url) => fetch(url),
  base: SITE_ROOT,
});

let queue = Promise.resolve();
self.onmessage = (event) => {
  // Messages are handled one after the other, in order of arrival.
  queue = queue.then(() => session.handle(event.data)).catch(() => {
    self.postMessage({ type: 'erreur', code: 'interne', message: 'Erreur inattendue du moteur de recherche.' });
  });
};
