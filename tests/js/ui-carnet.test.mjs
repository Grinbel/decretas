import { test } from 'node:test';
import assert from 'node:assert/strict';

import { CLE_STOCKAGE, creerCarnet, stockageDuNavigateur } from '../../site/js/donnees/carnet.js';

/** A Storage double; "casse" makes every call throw, like a blocked storage. */
function faux({ casse = false, plein = false } = {}) {
  const m = new Map();
  return {
    m,
    getItem(k) { if (casse) throw new Error('SecurityError'); return m.has(k) ? m.get(k) : null; },
    setItem(k, v) { if (casse || plein) throw new Error('QuotaExceededError'); m.set(k, String(v)); },
    removeItem(k) { if (casse) throw new Error('SecurityError'); m.delete(k); },
  };
}
const A = 'FRAN_IR_000001/DEC001';
const B = 'FRAN_IR_000001/DEC002';

test('carnet: ticks are kept under one key, with the date, and survive a new page', () => {
  const s = faux();
  const c = creerCarnet({ stockage: s, aujourdhui: () => '2026-11-12' });
  assert.equal(c.persistant, true);
  assert.equal(c.marquer(A, true), true);
  c.marquer(B, true);
  c.marquer(B, false);
  assert.deepEqual(JSON.parse(s.m.get(CLE_STOCKAGE)), { v: 1, lus: { [A]: '2026-11-12' } });
  const d = creerCarnet({ stockage: s });
  assert.equal(d.estLu(A), true);
  assert.equal(d.estLu(B), false);
  assert.equal(d.lus().get(A), '2026-11-12');
});

test('carnet: erasing removes the key entirely', () => {
  const s = faux();
  const c = creerCarnet({ stockage: s });
  c.marquer(A, true);
  c.effacer();
  assert.equal(c.taille(), 0);
  assert.equal(s.m.has(CLE_STOCKAGE), false);
});

test('carnet: only decree keys are accepted; a damaged value is ignored, never trusted', () => {
  const s = faux();
  const c = creerCarnet({ stockage: s });
  assert.equal(c.marquer('<img src=x>', true), false);
  assert.equal(c.marquer('FRAN_IR_1/x', true), false);
  s.m.set(CLE_STOCKAGE, '{pas du json');
  assert.equal(creerCarnet({ stockage: s }).taille(), 0);
  s.m.set(CLE_STOCKAGE, JSON.stringify({ v: 1, lus: { [A]: 'hier', 'javascript:x': '2026-01-01' } }));
  const d = creerCarnet({ stockage: s });
  assert.deepEqual([...d.lus()], [[A, null]]);
  s.m.set(CLE_STOCKAGE, JSON.stringify({ v: 2, lus: { [A]: '2026-01-01' } }));
  assert.equal(creerCarnet({ stockage: s }).taille(), 0, 'an unknown version is not read');
});

test('carnet: without storage (private window, blocked), the list works for the open page and says it is not kept', () => {
  const sans = creerCarnet({ stockage: null });
  assert.equal(sans.persistant, false);
  sans.marquer(A, true);
  assert.equal(sans.estLu(A), true);
  const casse = creerCarnet({ stockage: faux({ casse: true }) });
  assert.equal(casse.taille(), 0);
  casse.marquer(A, true);
  assert.equal(casse.estLu(A), true);
  assert.equal(casse.persistant, false, 'a failed write is admitted');
  const plein = creerCarnet({ stockage: faux({ plein: true }) });
  plein.marquer(A, true);
  assert.equal(plein.persistant, false);
});

test('carnet: subscribers are told of every change', () => {
  const c = creerCarnet({ stockage: faux() });
  let n = 0;
  const stop = c.abonner(() => { n += 1; });
  c.marquer(A, true);
  c.effacer();
  stop();
  c.marquer(A, true);
  assert.equal(n, 2);
});

test('carnet: in Node there is no browser storage, and asking for it does not throw', () => {
  assert.equal(stockageDuNavigateur(), null);
});
