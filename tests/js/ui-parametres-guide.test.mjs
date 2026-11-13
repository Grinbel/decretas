import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  designeUnDecretAn, designeUnePageBulletin, lireParametresGuide, parametresPourDecretAn, parametresPourPageBulletin, variablesDeLiens,
} from '../../site/js/logique/parametres-guide.js';
import { analyserHash, formerHash } from '../../site/js/routeur.js';

test('guide parameters: identifiers of a known shape are kept, anything else is dropped', () => {
  const p = lireParametresGuide({
    inventaire: 'FRAN_IR_000001', notice: 'DEC001', annee: '1905', date: '1905-03-01', cote: 'BB/34/900', document: 'document 4',
    feuillet: '12', page: '7', autre: 'x', q: 'Testaoui',
  });
  assert.deepEqual(p, { inventaire: 'FRAN_IR_000001', notice: 'DEC001', annee: '1905', feuillet: '12', page: '7', date: '1905-03-01', cote: 'BB/34/900', document: 'document 4' });
  assert.deepEqual(lireParametresGuide({ inventaire: 'FRAN_IR_1', notice: 'a b', date: '1905-3-1', cote: 'Décret du 1er mai 1905' }), {});
  assert.deepEqual(lireParametresGuide(undefined), {});
  assert.equal(designeUnDecretAn(p), true);
  assert.equal(designeUnePageBulletin(p), true);
  assert.equal(designeUnDecretAn({ inventaire: 'FRAN_IR_000001' }), false);
});

test('guide parameters: link variables, the date split as the templates want it', () => {
  assert.deepEqual(variablesDeLiens({ inventaire: 'FRAN_IR_000001', notice: 'N1', date: '1924-07-14' }),
    { inventaire: 'FRAN_IR_000001', notice: 'N1', date: '19240714', annee: '1924', mois: '07', jour: '14' });
  assert.deepEqual(variablesDeLiens({ cote: 'BB/34/1' }), {}, 'a call number fills no template');
});

test('guide parameters: from a decree and from a Bulletin entry, through an address and back', () => {
  const decret = { inv: 'FRAN_IR_000001', notice: 'DEC001', annee: 1885, date: '1885-03-10', cote: 'BB/34/900', doc: 'document 4' };
  const p = parametresPourDecretAn(decret);
  const route = analyserHash(formerHash('guides', ['an-annee-indexee'], p));
  assert.deepEqual(route.segments, ['an-annee-indexee']);
  assert.deepEqual(lireParametresGuide(route.params), { inventaire: 'FRAN_IR_000001', notice: 'DEC001', annee: '1885', date: '1885-03-10', cote: 'BB/34/900', document: 'document 4' });
  assert.deepEqual(parametresPourDecretAn({ inv: 'FRAN_IR_000001', notice: 'DEC002', annee: 1913, date: null, cote: 'cote illisible', doc: null }),
    { inventaire: 'FRAN_IR_000001', notice: 'DEC002', annee: 1913, date: null, cote: null, document: null });
  assert.deepEqual(parametresPourDecretAn(null), {});
  assert.deepEqual(parametresPourPageBulletin({ volume: { annee: 1888 }, feuille: 40, page: 31 }), { annee: 1888, feuillet: 40, page: 31 });
  assert.deepEqual(parametresPourPageBulletin({ volume: null, feuille: 40 }), {});
});
