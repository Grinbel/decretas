import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createSession } from '../../site/js/recherche/session.js';

const AN = JSON.stringify({
  champs: ['id', 'nom', 'an'],
  lignes: [['a1', 'Testaoui, Belkacem ben Chabane', 1876], ['a2', 'Testaoui, Mohamed', 1880]],
});
const BOGGA = JSON.stringify({
  champs: ['id', 'nom', 'an'],
  lignes: [['b1', 'Ali bon Slimane Exemplaoui', null]],
});

/** A fetch that serves in-memory files; "chunked" streams the body in pieces. */
function fakeFetch(files, { chunked = false } = {}) {
  return async (url) => {
    if (!(url in files)) return { ok: false, status: 404, headers: new Map(), text: async () => '' };
    const text = files[url];
    if (!chunked) return { ok: true, status: 200, headers: new Map(), text: async () => text };
    const bytes = new TextEncoder().encode(text);
    const stream = new ReadableStream({
      start(controller) {
        for (let i = 0; i < bytes.length; i += 40) controller.enqueue(bytes.slice(i, i + 40));
        controller.close();
      },
    });
    return { ok: true, status: 200, headers: new Map([['content-length', String(bytes.length)]]), body: stream };
  };
}

function session(files, options) {
  const out = [];
  const s = createSession({ post: (m) => out.push(m), fetch: fakeFetch(files, options) });
  return { out, handle: s.handle };
}

const FILES = { 'data/an-personnes.json': AN, 'data/bogga-entrees.json': BOGGA };
const CHARGER = {
  type: 'charger',
  fichiers: [{ url: 'data/an-personnes.json', groupe: 'an' }, { url: 'data/bogga-entrees.json', groupe: 'bogga', ocr: true }],
};

test('etat before loading; chercher before loading is refused', async () => {
  const { out, handle } = session(FILES);
  await handle({ type: 'etat' });
  assert.deepEqual(out[0], { type: 'etat', charge: false, enCours: false, index: null, fichiers: [] });
  await handle({ type: 'chercher', id: 7, requete: 'Testaoui' });
  assert.deepEqual(out[1], { type: 'erreur', id: 7, code: 'non-charge', message: "Les données ne sont pas encore chargées." });
});

test('charger: progress events, then pret; chercher, suggerer, etat', async () => {
  const { out, handle } = session(FILES, { chunked: true });
  await handle(CHARGER);
  const types = out.map((m) => m.type);
  assert.equal(types[types.length - 1], 'pret');
  const progress = out.filter((m) => m.type === 'progression');
  assert.ok(progress.length >= 6);
  assert.deepEqual([...new Set(progress.map((m) => m.etape))], ['telechargement', 'lecture', 'index']);
  const downloads = progress.filter((m) => m.etape === 'telechargement' && m.fichier === 'data/an-personnes.json');
  assert.ok(downloads.length > 2, 'one event per chunk received');
  const last = downloads[downloads.length - 1];
  assert.equal(last.recus, last.total);
  assert.deepEqual([last.numero, last.sur], [1, 2]);
  for (let i = 1; i < downloads.length; i++) assert.ok(downloads[i].recus >= downloads[i - 1].recus);

  const ready = out[out.length - 1];
  assert.equal(ready.index.occurrences, 3);
  assert.deepEqual(ready.index.parGroupe, { an: 2, bogga: 1 });
  assert.deepEqual(ready.index.groupesOcr, ['bogga']);
  assert.deepEqual(ready.fichiers[0], {
    url: 'data/an-personnes.json', groupe: 'an', lignes: 2, occurrences: 2, sansNom: 0, colonnes: { nom: ['nom'], id: 'id', annee: 'an' },
  });

  out.length = 0;
  await handle({ type: 'chercher', id: 'q1', requete: { texte: 'Testaoui Belkacem', annee: 1876 }, options: { limite: 5 } });
  assert.equal(out[0].type, 'correspondances');
  assert.equal(out[0].id, 'q1');
  assert.deepEqual(out[0].correspondances.map((r) => [r.id, r.classe]), [['a1', 'correspondance'], ['a2', 'partielle']]);
  assert.equal(out[0].bilan.comptes.total, 2);
  assert.doesNotThrow(() => structuredClone(out[0]), 'a reply must survive postMessage');

  await handle({ type: 'chercher', id: 'q2', requete: 'Benslimane Ali' });
  assert.deepEqual(out[1].correspondances.map((r) => r.id), ['b1'], 'the printed group reads "bon" as "ben"');

  await handle({ type: 'suggerer', id: 's1', terme: 'Belkacem' });
  assert.equal(out[2].type, 'suggestions');
  assert.deepEqual(out[2].suggestions.exactes.map((e) => e.graphie), ['Belkacem']);

  await handle({ type: 'etat' });
  assert.equal(out[3].charge, true);
  assert.equal(out[3].index.occurrences, 3);
});

test('charger: a missing file, bad JSON and a bad shape give French error messages', async () => {
  const missing = session({});
  await missing.handle(CHARGER);
  const e1 = missing.out[missing.out.length - 1];
  assert.deepEqual([e1.type, e1.code], ['erreur', 'chargement']);
  assert.match(e1.message, /an-personnes\.json.*404/);

  const broken = session({ 'data/an-personnes.json': '{"champs": [', 'data/bogga-entrees.json': BOGGA });
  await broken.handle(CHARGER);
  const e2 = broken.out[broken.out.length - 1];
  assert.deepEqual([e2.type, e2.code], ['erreur', 'format']);
  assert.match(e2.message, /JSON/);

  const shape = session({ 'data/an-personnes.json': '{"champs": ["x"], "lignes": []}', 'data/bogga-entrees.json': BOGGA });
  await shape.handle(CHARGER);
  const e3 = shape.out[shape.out.length - 1];
  assert.equal(e3.code, 'format');
  assert.match(e3.message, /Aucune colonne reconnue/);

  await shape.handle({ type: 'etat' });
  assert.equal(shape.out[shape.out.length - 1].charge, false, 'a failed load leaves no half-built index');

  const empty = session(FILES);
  await empty.handle({ type: 'charger', fichiers: [] });
  assert.equal(empty.out[0].code, 'chargement');
});

test('a network failure is reported without a stack trace', async () => {
  const out = [];
  const s = createSession({ post: (m) => out.push(m), fetch: async () => { throw new TypeError('fetch failed: ECONNREFUSED 10.0.0.1'); } });
  await s.handle(CHARGER);
  const e = out[out.length - 1];
  assert.equal(e.code, 'chargement');
  assert.ok(!/ECONNREFUSED|10\.0\.0\.1|at /.test(e.message));
});

test('unknown messages are refused', async () => {
  const { out, handle } = session(FILES);
  await handle({ type: 'supprimer' });
  await handle(null);
  assert.deepEqual(out.map((m) => m.code), ['message-inconnu', 'message-inconnu']);
});
