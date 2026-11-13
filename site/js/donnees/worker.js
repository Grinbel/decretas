/**
 * Data Web Worker: a thin wrapper around donnees/service.js, which documents the protocol.
 * Started as a module worker by donnees/client.js. Relative file URLs are resolved against
 * the site root (two levels above this file), not against this script.
 */

import { creerService } from './service.js';

const SITE_ROOT = typeof self.location === 'object' && self.location !== null && typeof self.location.href === 'string'
  ? new URL('../../', self.location.href).href
  : null;

const service = creerService({
  post: (message) => self.postMessage(message),
  fetch: (url) => fetch(url, { credentials: 'omit' }),
  base: SITE_ROOT,
});

let queue = Promise.resolve();
self.onmessage = (event) => {
  // One message at a time, in order of arrival.
  queue = queue.then(() => service.handle(event.data)).catch(() => {
    self.postMessage({ type: 'erreur', code: 'interne', id: event.data?.id });
  });
};
