import { test } from 'node:test';
import assert from 'node:assert/strict';

import { avertissements, expliquer, expliquerTerme } from '../../site/js/logique/explications.js';
import { search } from '../../site/js/recherche/chercher.js';
import { indexOf } from './aide.mjs';

const plat = (s) => s.replace(/ /g, ' ');

function seul(nom, requete) {
  const { correspondances } = search(indexOf([nom]), requete);
  assert.equal(correspondances.length, 1, `${requete} -> ${nom}`);
  return correspondances[0];
}

test('explanations: a word written as typed', () => {
  const [e] = expliquer(seul('Testaoui, Ali', 'Testaoui'));
  assert.equal(e.identique, true);
  assert.equal(e.approchant, false);
  assert.equal(plat(e.court), '« Testaoui », écrit comme vous l\'avez saisi');
});

test('explanations: a writing habit (k1) is the same name, and both spellings are shown', () => {
  const e = expliquer(seul('Testaoui, Mohammed', 'Mohamed Testaoui')).find((x) => x.terme === 'Mohamed');
  assert.equal(e.identique, false);
  assert.equal(e.approchant, false);
  assert.equal(plat(e.court), '« Mohammed » pour Mohamed');
  assert.match(e.detail, /habitude d'écriture/);
});

test('explanations: an approximate spelling says so, with the two spellings side by side', () => {
  const c = seul('Testaoui, Belgacem', 'Belkacem Testaoui');
  assert.equal(c.classe, 'graphie-approchante');
  const e = expliquer(c).find((x) => x.terme === 'Belkacem');
  assert.equal(e.approchant, true);
  assert.equal(plat(e.court), 'graphie approchante : Belgacem ≈ Belkacem');
  assert.match(e.detail, /charpente de consonnes/);
});

test('explanations: a missing term is named', () => {
  const c = seul('Testaoui, Belkacem', 'Belkacem Exemplane Testaoui');
  assert.equal(c.classe, 'partielle');
  const e = expliquer(c).find((x) => x.absent);
  assert.equal(e.terme, 'Exemplane');
  assert.equal(plat(e.court), '« Exemplane » n\'y figure pas');
});

test('explanations: glued and detached forms are explained in words', () => {
  const colle = expliquer(seul('Benexemplane, Ali', 'Ali ben Exemplane')).find((x) => x.terme === 'Exemplane');
  assert.equal(colle.approchant, false);
  assert.match(colle.detail, /collé/);
  const prefixe = expliquer(seul('Benexemplane, Ali', 'Ali Exemplane')).find((x) => x.terme === 'Exemplane');
  assert.equal(prefixe.approchant, true);
  assert.match(plat(prefixe.detail), /porte en plus « ben »/);
});

test('explanations: Arabic input is always approximate, and says how the vowels compare', () => {
  const c = seul('Testaoui, Belkacem', 'بلقاسم');
  assert.equal(c.classe, 'graphie-approchante');
  const [e] = expliquer(c);
  assert.equal(e.approchant, true);
  assert.match(e.detail, /saisie en arabe/);
});

test('explanations: unknown shapes do not throw', () => {
  assert.deepEqual(expliquer(null), []);
  assert.equal(expliquerTerme({ terme: 'X', absent: true }).absent, true);
});

test('warnings: the engine codes become sentences; two particles in a row is marked as important', () => {
  const { bilan } = search(indexOf(['Testaoui, Ahmed']), 'Bel Hadj Ahmed');
  const notes = avertissements(bilan.avertissements);
  const particules = notes.find((n) => n.code === 'compose-de-particules');
  assert.ok(particules, 'the engine warns about « Bel Hadj »');
  assert.equal(particules.important, true);
  assert.match(plat(particules.texte), /écrivez-le collé : « Belhadj »/);
  const nombre = avertissements(search(indexOf(['Testaoui, Ali']), '12 Testaoui').bilan.avertissements);
  assert.equal(nombre.some((n) => n.code === 'nombre-ignore' && !n.important && /« 12 »/.test(plat(n.texte))), true);
  assert.deepEqual(avertissements([{ code: 'code-futur', detail: 'x' }]), []);
  assert.deepEqual(avertissements(undefined), []);
});
