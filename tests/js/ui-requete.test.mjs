import { test } from 'node:test';
import assert from 'node:assert/strict';

import { basculer, etatDepuisParametres, lireAnnee, parametresDepuisEtat, preparerRequete, titreCourt } from '../../site/js/logique/requete.js';
import { analyserHash, formerHash } from '../../site/js/routeur.js';
import { indexOf } from './aide.mjs';
import { search } from '../../site/js/recherche/chercher.js';

test('query: without toggles the typed text goes to the engine untouched', () => {
  assert.deepEqual(preparerRequete({ texte: 'Belkacem ben Exemplane', annee: 1852 }), { entree: { texte: 'Belkacem ben Exemplane', annee: 1852 }, fidele: true });
  assert.deepEqual(preparerRequete({ texte: '' }), { entree: { texte: '' }, fidele: true });
});

test('query: a spelling set aside is excluded on its own term, the particle context is kept', () => {
  const { entree, fidele } = preparerRequete({ texte: 'Belkacem ben Exemplane', exclusions: { 0: ['belgacem'] } });
  assert.equal(fidele, true);
  assert.equal(entree.texte, 'Belkacem|-belgacem ben Exemplane');
  const index = indexOf(['Testaoui, Belgacem ben Exemplane', 'Testaoui, Belkacem Benexemplane']);
  const pleines = (requete) => search(index, requete).correspondances.filter((c) => c.classe !== 'partielle').map((c) => c.nom).sort();
  assert.deepEqual(pleines(preparerRequete({ texte: 'Belkacem ben Exemplane' }).entree), ['Testaoui, Belgacem ben Exemplane', 'Testaoui, Belkacem Benexemplane']);
  // set aside, "Belgacem" no longer stands for the term: that notice is at best a partial correspondence
  assert.deepEqual(pleines(entree), ['Testaoui, Belkacem Benexemplane']);
});

test('query: a related name ticked becomes a variant of its term', () => {
  const { entree, fidele } = preparerRequete({ texte: 'Mohamed Testaoui', ajouts: { 0: ['Mohand'] } });
  assert.equal(fidele, true);
  assert.equal(entree.texte, 'Mohamed|Mohand Testaoui');
  const index = indexOf(['Testaoui, Mohand', 'Testaoui, Ali']);
  assert.deepEqual(search(index, entree).correspondances.filter((c) => c.classe === 'correspondance').map((c) => c.nom), ['Testaoui, Mohand']);
});

test('query: the second term of a hyphenated word can be toggled too', () => {
  const { entree, fidele } = preparerRequete({ texte: 'Jean-Pierre Fictifi', exclusions: { 1: ['piere'] } });
  assert.equal(fidele, true);
  assert.equal(entree.texte, 'Jean Pierre|-piere Fictifi');
});

test('query: a toggle that cannot be applied is given up and said, never applied to the wrong term', () => {
  const out = preparerRequete({ texte: 'Belkacem', exclusions: { 3: ['x'] } });
  assert.equal(out.fidele, false);
  assert.equal(out.entree.texte, 'Belkacem');
  // values that would break the syntax are dropped before anything else
  assert.deepEqual(preparerRequete({ texte: 'Belkacem', exclusions: { 0: ['a|b', 'c d', '"'] } }), { entree: { texte: 'Belkacem' }, fidele: true });
});

test('query: the birth year is four digits in a plausible span, or nothing', () => {
  assert.equal(lireAnnee('1852'), 1852);
  assert.equal(lireAnnee(' 1852 '), 1852);
  for (const bad of ['', '76', '18526', 'vers 1852', '1699', '1963', null]) assert.equal(lireAnnee(bad), null, String(bad));
});

test('query: the state of a search survives the round trip through the address', () => {
  const etat = { texte: 'Belkacem ben Exemplane Testaoui', coupe: false, annee: 1852, anneeSaisie: '1852', tolerance: 10, exclusions: { 0: ['belgacem', 'belkecem'], 2: ['testaouy'] }, ajouts: { 1: ['Exemplaane'] } };
  const hash = formerHash('recherche', [], parametresDepuisEtat(etat));
  assert.deepEqual(etatDepuisParametres(analyserHash(hash).params), etat);
  assert.equal(hash.includes('tol=10'), true);
});

test('query: junk in the address gives a harmless state', () => {
  const etat = etatDepuisParametres({ q: 'x'.repeat(1000), ne: '<b>', tol: '9999', x: '~~0.~abc~12.', v: null });
  assert.equal(etat.texte.length, 300);
  assert.equal(etat.coupe, true, 'a name cut to 300 characters is said to be cut');
  assert.equal(etat.annee, null);
  assert.equal(etat.tolerance, null);
  assert.deepEqual(etat.exclusions, {});
  assert.deepEqual(etatDepuisParametres({}), { texte: '', coupe: false, annee: null, anneeSaisie: '', tolerance: null, exclusions: {}, ajouts: {} });
});

test('query: the tab title never carries more than a short form of the name', () => {
  assert.equal(titreCourt('Ali ben Exemple'), 'Ali ben Exemple');
  const long = titreCourt('Mohamed '.repeat(5000));
  assert.ok(long.length <= 80, String(long.length));
  assert.ok(long.endsWith('…'));
  assert.equal(titreCourt(undefined), '');
});

test('query: toggling returns a new map and removes empty entries', () => {
  const a = basculer({}, 0, ['belgacem'], true);
  assert.deepEqual(a, { 0: ['belgacem'] });
  const b = basculer(a, 0, ['belgacem'], false);
  assert.deepEqual(b, {});
  assert.deepEqual(a, { 0: ['belgacem'] });
});
