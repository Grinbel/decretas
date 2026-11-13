import { test } from 'node:test';
import assert from 'node:assert/strict';

import { apercuDesGraphies } from '../../site/js/composants/variantes.js';
import { libelleGraphie } from '../../site/js/logique/formats.js';
import { search } from '../../site/js/recherche/chercher.js';
import { indexOf } from './aide.mjs';

test('spellings: the one-line preview names the spellings of the same name first, then the approaching ones, marked; never the one typed', () => {
  const index = indexOf(['Testaoui, Belkacem', 'Fictifi, Belkacem', 'Testaoui, Belgacem', 'Exemplaoui, Belgacem', 'Fictifi, Belgacem', 'Testaoui, Belkassem']);
  const { bilan } = search(index, 'Belkacem');
  const apercu = apercuDesGraphies(bilan.graphiesTrouvees);
  // Regression: « Mahmoud » was listed for « Mohamed » as if it were a spelling of the same name.
  assert.deepEqual(apercu, [{ graphie: 'Belkassem', occurrences: 1, approchante: false }, { graphie: 'Belgacem', occurrences: 3, approchante: true }]);
  assert.deepEqual(apercuDesGraphies(bilan.graphiesTrouvees, 1), [{ graphie: 'Belkassem', occurrences: 1, approchante: false }]);
});

test('spellings: Mohamed and Mahmoud are never shown as the same name in the preview', () => {
  const index = indexOf(['Testaoui, Mohamed', 'Fictifi, Mohammed', 'Testaoui, Mahmoud', 'Exemplaoui, Mahmoud', 'Fictifi, Mahmoud']);
  const { bilan } = search(index, 'Mohamed');
  const parNom = Object.fromEntries(apercuDesGraphies(bilan.graphiesTrouvees).map((a) => [a.graphie, a.approchante]));
  assert.equal(parNom.Mohammed, false);
  assert.equal(parNom.Mahmoud, true);
});

test('spellings: nothing to preview when the sources only write the name as typed', () => {
  const { bilan } = search(indexOf(['Testaoui, Ali']), 'Testaoui');
  assert.deepEqual(apercuDesGraphies(bilan.graphiesTrouvees), []);
  assert.deepEqual(apercuDesGraphies(undefined), []);
});

test('spellings: a line that stands for several written words is shown with slashes, not commas', () => {
  assert.equal(libelleGraphie({ graphie: 'Benfictif, Fictifben', exclure: ['benfictif', 'fictifben'] }), 'Benfictif / Fictifben');
  assert.equal(libelleGraphie({ graphie: 'Belgacem', exclure: ['belgacem'] }), 'Belgacem');
  assert.equal(libelleGraphie({ graphie: 'Belgacem' }), 'Belgacem');
  assert.equal(libelleGraphie(null), '');
  const preview = apercuDesGraphies([{ terme: 'Fictif', graphies: [
    { graphie: 'Fictif', exclure: ['fictif'], niveau: 'k0', soudure: null, arabe: false, occurrences: 9 },
    { graphie: 'Benfictif, Fictifben', exclure: ['benfictif', 'fictifben'], niveau: 'k0', soudure: 'prefixe-source', arabe: false, occurrences: 4 },
  ] }]);
  assert.deepEqual(preview, [{ graphie: 'Benfictif / Fictifben', occurrences: 4, approchante: true }]);
});
