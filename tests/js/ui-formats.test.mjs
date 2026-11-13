import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  anneeDe, compacterAnnees, enDeuxTemps, enoncerAnnees, enoncerTrimestres, enumerer, formaterDate, formaterNombre,
  lireAnneesCompactes, plagesAnnees, remplirGabarit,
} from '../../site/js/logique/formats.js';
import { typographier, typographierTout } from '../../site/js/textes/typographie.js';

const NBSP = ' ';

test('formats: numbers get a narrow no-break space every three digits', () => {
  assert.equal(formaterNombre(62123), '62 123');
  assert.equal(formaterNombre(999), '999');
  assert.equal(formaterNombre(1234567), '1 234 567');
  assert.equal(formaterNombre(NaN), '');
  assert.equal(formaterNombre('12'), '');
});

test('formats: an ISO date is written in French; anything else is returned untouched', () => {
  assert.equal(formaterDate('1913-07-26'), '26 juillet 1913');
  assert.equal(formaterDate('1850-01-01'), '1er janvier 1850');
  assert.equal(formaterDate('1913-13-01'), '1913-13-01');
  assert.equal(formaterDate('40 mars 1885'), '40 mars 1885');
  assert.equal(formaterDate(null), '');
  assert.equal(anneeDe('1913-07-26'), 1913);
  assert.equal(anneeDe(undefined), null);
});

test('formats: years are grouped into ranges and said in words', () => {
  assert.deepEqual(plagesAnnees([1885, 1883, 1884, 1899, 1884]), [[1883, 1885], [1899, 1899]]);
  assert.equal(enoncerAnnees([1883, 1884, 1885, 1899, 1933, 1934]), '1883 à 1885, 1899, 1933 et 1934');
  assert.equal(enoncerAnnees([]), '');
  assert.equal(enumerer(['a', 'b', 'c']), 'a, b et c');
});

test('formats: the compact form of a list of years survives the round trip, and refuses nonsense', () => {
  const years = [1899, 1900, 1901, 1928, 1933, 1934, 1935];
  assert.equal(compacterAnnees(years), '1899-1901,1928,1933-1935');
  assert.deepEqual(lireAnneesCompactes(compacterAnnees(years)), years);
  assert.deepEqual(lireAnneesCompactes('1948-1899,abc,1900-9999,<script>,1933'), [1933]);
  assert.deepEqual(lireAnneesCompactes(undefined), []);
});

test('formats: quarters become months, neighbours merged', () => {
  assert.deepEqual(enoncerTrimestres([2, 3, 4]), ['avril à décembre']);
  assert.deepEqual(enoncerTrimestres([1, 3]), ['janvier à mars', 'juillet à septembre']);
});

test('formats: an unknown variable of a template stays visible rather than vanishing', () => {
  assert.equal(remplirGabarit('Années {annees_an}, {inconnue}.', { annees_an: '1883 à 1897' }), 'Années 1883 à 1897, {inconnue}.');
});

test('typography: no-break spaces inside guillemets and before double punctuation', () => {
  assert.equal(typographier('Le mot « indigène » : voir ; quoi ? oui !'), `Le mot «${NBSP}indigène${NBSP}»${NBSP}: voir${NBSP}; quoi${NBSP}? oui${NBSP}!`);
  // an address or a time is not French punctuation
  assert.equal(typographier('https://exemple.test/a?b=c'), 'https://exemple.test/a?b=c');
});

test('typography: applied to strings and to what functions return; listed keys are left alone', () => {
  const out = typographierTout({ a: 'Que faire ?', f: (n) => `${n} : oui`, gabarit: 'x ?y', n: 3, l: ['a ; b'] }, (k) => k === 'gabarit');
  assert.equal(out.a, `Que faire${NBSP}?`);
  assert.equal(out.f(2), `2${NBSP}: oui`);
  assert.equal(out.gabarit, 'x ?y');
  assert.equal(out.n, 3);
  assert.deepEqual(out.l, [`a${NBSP}; b`]);
});

test('formats: a long paragraph is cut after its first sentence, and nothing of it is lost', () => {
  const texte = 'Nous n\'avons trouvé aucune correspondance. C\'est le résultat le plus fréquent : il y a une raison. Voici la suite.';
  const parts = enDeuxTemps(texte);
  assert.equal(parts.length, 2);
  assert.equal(parts[0], 'Nous n\'avons trouvé aucune correspondance.');
  assert.equal(parts.join(' '), texte);
  assert.deepEqual(enDeuxTemps('Une seule phrase.'), ['Une seule phrase.']);
  assert.deepEqual(enDeuxTemps(null), ['']);
});
