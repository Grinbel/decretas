import { test } from 'node:test';
import assert from 'node:assert/strict';

import { analyserHash, formerHash } from '../../site/js/routeur.js';

test('router: anything that is not "#/…" is the home page', () => {
  for (const hash of ['', '#', '#contenu', 'recherche', null, undefined]) {
    assert.deepEqual(analyserHash(hash), { nom: '', segments: [], params: {} });
  }
  assert.deepEqual(analyserHash('#/'), { nom: '', segments: [], params: {} });
});

test('router: name, segments and parameters', () => {
  assert.deepEqual(analyserHash('#/recherche?q=Belkacem+ben+Exemplane&ne=1852'), {
    nom: 'recherche', segments: [], params: { q: 'Belkacem ben Exemplane', ne: '1852' },
  });
  assert.deepEqual(analyserHash('#/guides/legifrance-jorf'), { nom: 'guides', segments: ['legifrance-jorf'], params: {} });
  assert.deepEqual(analyserHash('#/notice/an/FRAN_IR_000001/PERS001?m=2'), {
    nom: 'notice', segments: ['an', 'FRAN_IR_000001', 'PERS001'], params: { m: '2' },
  });
});

test('router: a search survives the round trip through the address, Arabic and punctuation included', () => {
  for (const q of ['Belkacem ben Exemplane Testaoui', 'بلقاسم بن شعبان', 'M\'Hamed|-Mahmoud "Hadj"', 'a&b=c?d#e/f%20+g']) {
    const hash = formerHash('recherche', [], { q, ne: 1852 });
    assert.ok(hash.startsWith('#/recherche?'));
    assert.deepEqual(analyserHash(hash).params, { q, ne: '1852' });
  }
});

test('router: empty parameters are left out; the first value of a repeated parameter wins', () => {
  assert.equal(formerHash('recherche', [], { q: 'Ali', ne: null, tol: '', x: undefined }), '#/recherche?q=Ali');
  assert.equal(formerHash(''), '#/');
  assert.equal(formerHash('guides', ['an-annee-indexee']), '#/guides/an-annee-indexee');
  assert.equal(analyserHash('#/recherche?q=un&q=deux').params.q, 'un');
});

test('router: a malformed escape does not throw', () => {
  assert.deepEqual(analyserHash('#/guides/%E0%A4%A'), { nom: 'guides', segments: ['%E0%A4%A'], params: {} });
});
