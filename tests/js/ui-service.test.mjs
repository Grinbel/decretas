import { test } from 'node:test';
import assert from 'node:assert/strict';

import { creerService, FICHIERS } from '../../site/js/donnees/service.js';
import { fichiers } from './ui-aide.mjs';

function monde({ absent = null, casse = null } = {}) {
  const f = fichiers();
  const parUrl = Object.fromEntries(FICHIERS.map((spec) => [spec.url, JSON.stringify(f[spec.cle])]));
  // sizes announced by the meta file, as the real one does
  f.anMeta.fichiers = { 'an-personnes.json': { octets: parUrl['data/an-personnes.json'].length }, 'an-decrets.json': { octets: parUrl['data/an-decrets.json'].length } };
  f.boggaMeta.fichiers = { 'bogga-entrees.json': { octets: parUrl['data/bogga-entrees.json'].length } };
  parUrl['data/an-meta.json'] = JSON.stringify(f.anMeta);
  parUrl['data/bogga-meta.json'] = JSON.stringify(f.boggaMeta);
  const demandes = [];
  const messages = [];
  const service = creerService({
    post: (m) => messages.push(m),
    fetch: async (url) => {
      demandes.push(url);
      if (url === absent) return { ok: false, status: 404 };
      const text = url === casse ? '{"champs": [' : parUrl[url];
      return { ok: true, status: 200, text: async () => text };
    },
  });
  return { service, messages, demandes };
}

test('service: loads the seven files of the site, reports progress, then says it is ready', async () => {
  const { service, messages, demandes } = monde();
  await service.handle({ type: 'charger' });
  assert.deepEqual([...demandes].sort(), FICHIERS.map((f) => f.url).sort());
  assert.equal(demandes.every((u) => u.startsWith('data/')), true, 'only the site\'s own data files are fetched');
  const types = messages.map((m) => m.type);
  assert.equal(types.at(-1), 'pret');
  assert.equal(types.filter((t) => t === 'pret').length, 1);
  const etapes = messages.filter((m) => m.type === 'progression').map((m) => m.etape);
  assert.deepEqual([...new Set(etapes)], ['telechargement', 'lecture', 'index']);
  const derniere = messages.filter((m) => m.type === 'progression' && m.etape === 'telechargement').at(-1);
  assert.ok(Number.isFinite(derniere.total) && derniere.recus <= derniere.total && derniere.recus > 0, 'a real total, never exceeded');
  const { resume } = messages.at(-1);
  assert.equal(resume.index.occurrences, 10);         // 6 names of the Archives nationales + 4 printed entries
  assert.equal(resume.couverture.an.noms, 6);
  // a second "charger" answers at once, without downloading again
  await service.handle({ type: 'charger' });
  assert.equal(demandes.length, 7);
  assert.equal(messages.at(-1).type, 'pret');
});

test('service: a search returns light correspondences and the notices they fall on, households joined', async () => {
  const { service, messages } = monde();
  await service.handle({ type: 'charger' });
  await service.handle({ type: 'chercher', id: 7, etat: { texte: 'Belkacem ben Exemplane', annee: 1850 } });
  const m = messages.at(-1);
  assert.equal(m.type, 'correspondances');
  assert.equal(m.id, 7);
  assert.equal(m.fidele, true);
  assert.deepEqual(m.correspondances.map((c) => [c.cle, c.classe]), [['an:0', 'correspondance'], ['bogga:2', 'correspondance']]);
  assert.deepEqual(Object.keys(m.fiches).sort(), ['an:0', 'bogga:2']);
  assert.equal(m.fiches['an:0'].membres.length, 4);
  assert.equal(m.fiches['an:0'].publications.length, 2);
  assert.equal(m.bilan.comptes.parGroupe.an.correspondance, 1);
  // a correspondence carries what the card needs to explain itself, not the whole occurrence
  assert.equal('occurrence' in m.correspondances[0], false);
  assert.ok(Array.isArray(m.correspondances[0].termes));
});

test('service: a spouse or a child found leads to the card of the household', async () => {
  const { service, messages } = monde();
  await service.handle({ type: 'charger' });
  await service.handle({ type: 'chercher', id: 1, etat: { texte: 'Fatma Exemplaoui' } });
  const m = messages.at(-1);
  assert.deepEqual(m.correspondances.filter((c) => c.classe === 'correspondance').map((c) => [c.cle, c.ligne]), [['an:0', 1]]);
  assert.equal(m.fiches['an:0'].membres[0].nom, 'Testaoui, Belkacem ben Exemplane');
});

test('service: related names are offered, never applied', async () => {
  const { service, messages } = monde();
  await service.handle({ type: 'charger' });
  await service.handle({ type: 'chercher', id: 2, etat: { texte: 'Mohand' } });
  const m = messages.at(-1);
  assert.equal(m.correspondances.length, 0, '« Mohamed ben Fictifi » is not a correspondence for « Mohand »');
  assert.deepEqual(m.apparentees[0].map((a) => a.graphie), ['Mohamed']);
});

test('service: a notice by its reference, and the decrees of a year', async () => {
  const { service, messages } = monde();
  await service.handle({ type: 'charger' });
  await service.handle({ type: 'fiche', id: 3, ref: { source: 'an', inv: 'FRAN_IR_000002', notice: 'PERS003' } });
  assert.equal(messages.at(-1).fiche.membres[0].nom, 'Testaoui, Larbi ould Rabah');
  await service.handle({ type: 'fiche', id: 4, ref: { source: 'an', inv: 'x', notice: 'y' } });
  assert.equal(messages.at(-1).fiche, null);
  await service.handle({ type: 'decrets-an', id: 5, filtre: { annees: [1933] } });
  assert.deepEqual(messages.at(-1).decrets.map((d) => d.notice), ['DEC003']);
});

test('service: a file that cannot be downloaded, or is not what is expected, gives an error code — never a half-built index', async () => {
  const a = monde({ absent: 'data/an-personnes.json' });
  await a.service.handle({ type: 'charger' });
  assert.deepEqual(a.messages.at(-1), { type: 'erreur', code: 'chargement', fichier: 'data/an-personnes.json', statut: 404 });
  await a.service.handle({ type: 'chercher', id: 1, etat: { texte: 'Ali' } });
  assert.deepEqual(a.messages.at(-1), { type: 'erreur', code: 'non-charge', id: 1 });

  const b = monde({ casse: 'data/bogga-entrees.json' });
  await b.service.handle({ type: 'charger' });
  assert.equal(b.messages.at(-1).code, 'format');

  const c = monde();
  await c.service.handle({ type: 'inconnu' });
  assert.deepEqual(c.messages.at(-1), { type: 'erreur', code: 'message-inconnu' });
  await c.service.handle(null);
  assert.equal(c.messages.at(-1).code, 'message-inconnu');
});
