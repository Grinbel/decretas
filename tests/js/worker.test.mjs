import { test } from 'node:test';
import assert from 'node:assert/strict';

// worker.js only needs the two globals of a Web Worker: "self" and "fetch". They are replaced
// here by stand-ins, so this checks the wiring, not a real browser.
test('worker.js: messages are handled in order through self.onmessage / self.postMessage', async () => {
  const data = JSON.stringify({ champs: ['id', 'nom', 'an'], lignes: [['a1', 'Testaoui, Belkacem ben Chabane', 1876]] });
  const posted = [];
  const previous = { self: globalThis.self, fetch: globalThis.fetch };
  globalThis.self = { postMessage: (m) => posted.push(m), onmessage: null };
  globalThis.fetch = async (url) => (url === 'data/an-personnes.json'
    ? { ok: true, status: 200, headers: new Map(), text: async () => data }
    : { ok: false, status: 404, headers: new Map(), text: async () => '' });
  try {
    await import('../../site/js/recherche/worker.js');
    assert.equal(typeof globalThis.self.onmessage, 'function');
    // Sent at once, before the data is loaded: the worker must queue them.
    globalThis.self.onmessage({ data: { type: 'charger', fichiers: [{ url: 'data/an-personnes.json', groupe: 'an' }] } });
    globalThis.self.onmessage({ data: { type: 'chercher', id: 1, requete: 'Testaoui Belkacem' } });
    globalThis.self.onmessage({ data: { type: 'etat' } });
    for (let i = 0; i < 200 && !posted.some((m) => m.type === 'etat'); i++) await new Promise((r) => setTimeout(r, 5));
    const types = posted.map((m) => m.type);
    assert.ok(types.indexOf('pret') >= 0 && types.indexOf('pret') < types.indexOf('correspondances'));
    assert.ok(types.indexOf('correspondances') < types.indexOf('etat'));
    const found = posted.find((m) => m.type === 'correspondances');
    assert.deepEqual(found.correspondances.map((c) => [c.id, c.classe]), [['a1', 'correspondance']]);
  } finally {
    globalThis.self = previous.self;
    globalThis.fetch = previous.fetch;
  }
});
