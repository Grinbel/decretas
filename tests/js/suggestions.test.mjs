import { test } from 'node:test';
import assert from 'node:assert/strict';

import { suggestVariants, RELATED_NAMES } from '../../site/js/recherche/suggestions.js';
import { search } from '../../site/js/recherche/chercher.js';
import { indexOf } from './aide.mjs';

const rows = [];
const add = (name, times) => { for (let i = 0; i < times; i++) rows.push([`Testaoui${rows.length}, ${name}`, 1850]); };
add('Belkacem', 5);
add('Belgacem', 3);
add('Belkassem', 2);
add('Bel Kacem', 1);
add('Kacem', 4);
add('Boulkacem', 1);
add('Aboulkacem', 1);
add('Mohamed', 6);
add('Mohammed', 4);
add('Mahmoud', 2);
add('Mohand', 3);
add('Ezzemri', 1);
add('Zemri', 2);
add('ben Ali', 2);
const INDEX = indexOf(rows);
const spell = (list) => list.map((e) => `${e.graphie} (${e.occurrences})`);

test('suggestions list the spellings actually present, with their frequencies', () => {
  const s = suggestVariants(INDEX, 'Belkacem');
  assert.equal(s.ecriture, 'latin');
  assert.deepEqual(s.cles, { k0: 'belkacem', k1: 'belkasem', k2: 'blksm' });
  assert.deepEqual(spell(s.exactes), ['Belkacem (6)'], '5 written in one word + 1 written "Bel Kacem"');
  assert.deepEqual(spell(s.memeEcriture), ['Belkassem (2)']);
  assert.deepEqual(spell(s.squelette), ['Belgacem (3)', 'Boulkacem (1)']);
  assert.deepEqual(spell(s.avecPrefixe), ['Kacem (5)'], '4 Kacem + the Kacem of "Bel Kacem"');
  assert.deepEqual(spell(s.apparentees), ['Aboulkacem (1)'], 'no spelling rule reaches it: suggested, not applied');
  assert.match(s.apparentees[0].raison, /Abou el Kacem/);
});

test('suggestions never propose a spelling absent from the index', () => {
  const s = suggestVariants(INDEX, 'Belkacem');
  const all = [...s.exactes, ...s.memeEcriture, ...s.squelette, ...s.avecPrefixe, ...s.apparentees];
  for (const e of all) assert.ok(e.occurrences > 0, e.graphie);
  const none = suggestVariants(INDEX, 'Introuvable');
  assert.deepEqual([none.exactes, none.memeEcriture, none.squelette, none.avecPrefixe, none.apparentees], [[], [], [], [], []]);
});

test('known skeleton collisions are shown so that the user can untick them', () => {
  const s = suggestVariants(INDEX, 'Mohamed');
  assert.deepEqual(spell(s.exactes), ['Mohamed (6)']);
  assert.deepEqual(spell(s.memeEcriture), ['Mohammed (4)']);
  assert.deepEqual(spell(s.squelette), ['Mahmoud (2)']);
  assert.deepEqual(spell(s.apparentees), ['Mohand (3)'], 'Mohand is only suggested, never applied');
  const before = search(INDEX, 'Mohamed').bilan.comptes.parClasse;
  assert.deepEqual(before, { correspondance: 10, 'graphie-approchante': 2, partielle: 0 });
  const after = search(INDEX, { termes: [{ variantes: ['Mohamed'], exclues: [s.squelette[0].forme] }] }).bilan.comptes.parClasse;
  assert.deepEqual(after, { correspondance: 10, 'graphie-approchante': 0, partielle: 0 });
  const added = search(INDEX, 'Mohamed|Mohand').bilan.comptes.parClasse;
  assert.equal(added.correspondance, 13);
});

test('prefix relatives are listed both ways', () => {
  assert.deepEqual(spell(suggestVariants(INDEX, 'Zemri').avecPrefixe), ['Ezzemri (1)']);
  assert.deepEqual(spell(suggestVariants(INDEX, 'Ezzemri').avecPrefixe), ['Zemri (2)']);
});

test('short words have no skeleton level; particles give nothing', () => {
  const ali = suggestVariants(INDEX, 'ben Ali');
  assert.equal(ali.cles.k2, null);
  assert.deepEqual(spell(ali.exactes), ['Ali (2)']);
  const particle = suggestVariants(INDEX, 'ben');
  assert.equal(particle.ecriture, null);
  assert.deepEqual(particle.exactes, []);
});

test('the list is cut at the limit and says so', () => {
  const many = [];
  for (let i = 0; i < 12; i++) many.push([`Testaoui, Bel${'a'.repeat(i + 1)}kacem`, 1850]);
  const s = suggestVariants(indexOf(many), 'Belkacem', { limite: 5 });
  assert.equal(s.squelette.length, 5);
  assert.equal(s.tronque, true);
});

test('the related-names table is well formed', () => {
  for (const g of RELATED_NAMES) {
    assert.ok(g.noms.length >= 2);
    assert.ok(g.raison.length > 10);
  }
});
