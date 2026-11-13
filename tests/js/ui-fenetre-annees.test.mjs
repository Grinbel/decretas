import { test } from 'node:test';
import assert from 'node:assert/strict';

import { conseilsPourAnnee, fenetreAdmission } from '../../site/js/logique/fenetre-annees.js';
import { creerModele } from '../../site/js/donnees/modele.js';
import { fichiers } from './ui-aide.mjs';

const couverture = creerModele(fichiers()).couverture();

test('year window: admission by decree from the minimum age on, up to the last year of the sources', () => {
  assert.deepEqual(fenetreAdmission(1876, { ageMinimal: 21, fin: 1948 }), { de: 1897, a: 1948 });
  assert.deepEqual(fenetreAdmission(1927, { ageMinimal: 21, fin: 1948 }), { de: 1948, a: 1948 });
  assert.equal(fenetreAdmission(1928, { ageMinimal: 21, fin: 1948 }), null);
  assert.equal(fenetreAdmission(null, { ageMinimal: 21, fin: 1948 }), null);
  assert.equal(fenetreAdmission(1876, { ageMinimal: undefined, fin: 1948 }), null);
});

test('year window: born about 1876 — the years to read on the images start at birth + 21', () => {
  const c = conseilsPourAnnee(couverture, 1876, 21);
  assert.equal(c.anneeMin, 1897);
  assert.deepEqual(c.fenetre, { de: 1897, a: 1934 }); // 1934: last year of the synthetic sources
  // 1899: images only; 1900 and 1928: a few names typed at the Archives nationales, not published here
  assert.deepEqual(c.imagesSeules, [1899, 1900, 1928, 1933, 1934]);
  assert.deepEqual(c.nomsAuxAn, [1898, 1900, 1928]);
  assert.deepEqual(c.lues, [1913]);
  assert.deepEqual(c.bulletinLu, []);     // 1873 and 1885 are before 1897
  assert.equal(c.horsSources, false);
});

test('year window: no year given — every year of the sources is listed, nothing is tailored', () => {
  const c = conseilsPourAnnee(couverture, null, 21);
  assert.equal(c.naissance, null);
  assert.equal(c.fenetre, null);
  assert.deepEqual(c.lues, [1885, 1913]);
  assert.deepEqual(c.bulletinLu, [1873, 1885]);
  assert.deepEqual(c.bulletinAbsent, [1862]);
});

test('year window: born too late for the sources — nothing to read here, and it is said', () => {
  const c = conseilsPourAnnee(couverture, 1930, 21);
  assert.equal(c.horsSources, true);
  assert.equal(c.apresSources, true);
  assert.deepEqual(c.imagesSeules, []);
  assert.deepEqual(c.lues, []);
});

test('year window: born early — the first possible year is before the first source', () => {
  const c = conseilsPourAnnee(couverture, 1830, 21);
  assert.equal(c.avantSources, true);
  assert.deepEqual(c.bulletinLu, [1873, 1885]);
});
