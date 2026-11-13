import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { creerLiens, imagePageBulletin, lienPageBulletin } from '../../site/js/logique/liens.js';
import { tableDeLiens, fichiersBogga } from './ui-aide.mjs';

const liens = creerLiens(tableDeLiens());

test('links: a template is filled from the table, and the data name {inv} is understood as {inventaire}', () => {
  const a = liens.resoudre('an-notice', { inv: 'FRAN_IR_000001', notice: 'c-6abc--12_x' });
  assert.equal(a.url, 'https://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_000001/c-6abc--12_x');
  assert.equal(a.hote, 'www.siv.archives-nationales.culture.gouv.fr');
  const b = liens.resoudre('an-notice', { inventaire: 'FRAN_IR_000001', notice: 'c-6abc--12_x' });
  assert.equal(b.url, a.url);
});

test('links: a link never seen working carries the honest note of the table and its fallback', () => {
  const a = liens.resoudre('an-notice', { inv: 'FRAN_IR_000001', notice: 'N1' });
  assert.equal(a.teste, false);
  assert.equal(a.statut, 'non-teste');
  assert.match(a.note, /Jamais vu fonctionner/);
  assert.equal(a.repli, 'an-inventaire');
  const tested = liens.resoudre('an-inventaire', { inv: 'FRAN_IR_000001' });
  assert.equal(tested.teste, true);
  assert.equal(tested.note, null);
});

test('links: without its own warning, an untested link gets the generic sentence, minus the pointer to hidden fields', () => {
  const a = liens.resoudre('recherche-mot', { identifiant: 'depot', mot: 'x' });
  assert.equal(a.proposer, false);
  assert.doesNotMatch(a.note, /observation/);
  assert.match(a.note, /Personne n'a encore vu/);
});

test('links: a missing or malformed variable gives no address at all', () => {
  assert.equal(liens.resoudre('an-notice', { inv: 'FRAN_IR_000001' }).url, null);
  assert.deepEqual(liens.resoudre('an-notice', { inv: 'FRAN_IR_000001' }).manquantes, ['notice']);
  for (const inv of ['FRAN_IR_1', '../../x', 'FRAN_IR_000001/../..', 'FRAN_IR_000001?x=1', 'javascript:alert(1)']) {
    assert.equal(liens.resoudre('an-inventaire', { inv }).url, null, inv);
  }
  for (const notice of ['a/b', 'a b', 'a"b', '<x>', 'a#b', 'a?b']) {
    assert.equal(liens.resoudre('an-notice', { inv: 'FRAN_IR_000001', notice }).url, null, notice);
  }
  assert.equal(liens.resoudre('inconnu', {}), null);
});

test('links: free text is encoded; a template that leaves its announced host is refused', () => {
  assert.equal(liens.resoudre('recherche-mot', { identifiant: 'depot', mot: 'ben Exemplane & co' }).url, 'https://archive.org/details/depot?q=ben%20Exemplane%20%26%20co');
  assert.equal(liens.resoudre('fixe').url, 'https://www.exemple.test/page');
  assert.equal(liens.resoudre('piege', { identifiant: 'x' }).url, null);
});

test('links: an address copied from a data file is accepted only on a known host, and never said tested', () => {
  const ok = liens.particulier('http://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_000002/ZZ9/autre');
  assert.equal(ok.teste, false);
  assert.equal(ok.hote, 'www.siv.archives-nationales.culture.gouv.fr');
  assert.equal(liens.particulier('https://ailleurs.test/x'), null);
  assert.equal(liens.particulier('javascript:alert(1)'), null);
  assert.equal(liens.particulier('https://user:pw@archive.org/x'), null);
  assert.equal(liens.particulier(null), null);
});

test('links: the page of a Bulletin volume uses the template that reproduces the address of the data file', () => {
  const { boggaVolumes } = fichiersBogga();
  const [seul, plusieurs] = boggaVolumes.lignes.map((r) => ({ item: r[1], doc: r[2], lienPage: r[5], imagePage: r[6] }));
  const a = lienPageBulletin(liens, seul, 640);
  assert.equal(a.id, 'ia-page');
  assert.equal(a.url, 'https://archive.org/details/bulletin_fictif_1873/page/n640/mode/1up');
  const b = lienPageBulletin(liens, plusieurs, 150);
  assert.equal(b.id, 'ia-page-volume');
  assert.equal(b.url, 'https://archive.org/details/depot-fictif/Tome%201885%20A/page/n150/mode/1up');
  // a data file that announces another address: nothing is invented
  assert.equal(lienPageBulletin(liens, { ...seul, lienPage: 'https://archive.org/autre/{leaf}' }, 3).url, null);
  assert.equal(lienPageBulletin(liens, seul, null), null);
});

test('links: the image of a page is only ever asked from https://archive.org', () => {
  const { boggaVolumes } = fichiersBogga();
  const vol = { imagePage: boggaVolumes.lignes[0][6] };
  assert.equal(imagePageBulletin(vol, 640, 1000), 'https://archive.org/download/bulletin_fictif_1873/page/n640_w1000.jpg');
  assert.equal(imagePageBulletin({ imagePage: 'https://ailleurs.test/n{leaf}.jpg' }, 1), null);
  assert.equal(imagePageBulletin({ imagePage: 'http://archive.org/n{leaf}.jpg' }, 1), null);
  assert.equal(imagePageBulletin(vol, '640'), null);
});

test('links: the real table of the site — the links of the results resolve, and none shown is unproposed', () => {
  const table = JSON.parse(readFileSync(new URL('../../site/contenu/liens.json', import.meta.url), 'utf8'));
  const reels = creerLiens(table);
  const params = { inv: 'FRAN_IR_000001', notice: 'DEC001', identifiant: 'depot-fictif', volume: 'Tome 1885 A', feuillet: 12 };
  for (const id of ['an-inventaire', 'an-notice', 'an-images-notice', 'ia-page', 'ia-page-volume', 'ia-volume']) {
    const r = reels.resoudre(id, params);
    assert.ok(r, id);
    assert.equal(r.proposer, true, id);
    assert.match(r.url, /^https:\/\//, id);
    assert.equal(new URL(r.url).hostname, r.hote, id);
    if (!r.teste) assert.ok(r.note && r.note.length > 20, `${id}: an untested link must carry a note`);
  }
  // every link of the table: an address only on its own host, in https
  for (const entry of table.liens) {
    if (entry.variables.length > 0) continue;
    const r = reels.resoudre(entry.id);
    assert.ok(r.url === null || new URL(r.url).hostname === entry.hote, entry.id);
  }
});
