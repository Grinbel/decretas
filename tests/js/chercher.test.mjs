import { test } from 'node:test';
import assert from 'node:assert/strict';

import { search, parseQuery, CLASSES, DEFAULT_TOLERANCE } from '../../site/js/recherche/chercher.js';
import { indexOf, classes, classOf } from './aide.mjs';

const A = 'correspondance';
const B = 'graphie-approchante';
const C = 'partielle';

// ---------------------------------------------------------------------------------------------
// Query parsing
// ---------------------------------------------------------------------------------------------
test('parseQuery: terms, particles, variants, quotes', () => {
  const q = parseQuery('Belkacem ben Chabane Testaoui');
  assert.deepEqual(q.termes.map((t) => t.libelle), ['Belkacem', 'Chabane', 'Testaoui']);
  assert.deepEqual(q.particulesIgnorees, [{ saisie: 'ben', particule: 'ben' }]);
  assert.equal(q.annee, null);
  assert.equal(q.tolerance, DEFAULT_TOLERANCE);

  const v = parseQuery('Belkacem|Belgacem | Belkassem Chabane');
  assert.equal(v.termes.length, 2);
  assert.deepEqual(v.termes[0].variantes.map((x) => x.saisie), ['Belkacem', 'Belgacem', 'Belkassem']);

  const forced = parseQuery('"Hadj" Ali');
  assert.deepEqual(forced.termes.map((t) => [t.libelle, t.exige]), [['Hadj', true], ['Ali', false]]);

  const excl = parseQuery('Slimane|-Salomon');
  assert.deepEqual(excl.termes[0].exclues, ['salomon']);
});

test('parseQuery: a typed particle is kept as a possible glued form of the next term', () => {
  const q = parseQuery('ben Chabane');
  const formes = q.termes[0].variantes[0].formes.map((f) => `${f.genre}:${f.k0}`);
  assert.deepEqual(formes, ['entier:chabane', 'colle:benchabane']);
  const glued = parseQuery('Benchabane').termes[0].variantes[0].formes.map((f) => `${f.genre}:${f.k0}`);
  assert.deepEqual(glued, ['entier:benchabane', 'decolle:chabane']);
  const abd = parseQuery('Abd-el-Kader').termes[0].variantes[0].formes.map((f) => `${f.genre}:${f.k0}`);
  assert.deepEqual(abd, ['entier:kader', 'colle:elkader', 'colle:abdelkader']);
});

test('parseQuery: a query is never expanded into a bare particle', () => {
  for (const text of ['Belhadj', 'Elhadj', 'Bensidi', 'Benelhadj']) {
    const formes = parseQuery(text).termes[0].variantes[0].formes;
    for (const f of formes) assert.ok(!['hadj', 'sidi', 'el', 'ben'].includes(f.k0), `${text} -> ${f.k0}`);
  }
});

test('parseQuery: only particles gives no term, and says how to write a glued family name', () => {
  const q = parseQuery('Bel Hadj');
  assert.equal(q.termes.length, 0);
  assert.ok(q.avertissements.some((a) => a.code === 'aucun-terme'));
  assert.ok(q.avertissements.some((a) => a.code === 'compose-de-particules' && a.detail === 'belhadj'));
});

test('parseQuery: structured input, year and tolerance', () => {
  const q = parseQuery({ termes: ['Belkacem|Belgacem', { variantes: ['Bel Hadi', 'Belhadi'] }], annee: '1876', tolerance: 3 });
  assert.deepEqual(q.termes.map((t) => t.libelle), ['Belkacem', 'Bel Hadi']);
  assert.deepEqual(q.termes[1].variantes[0].formes.map((f) => `${f.genre}:${f.k0}`), ['entier:hadi', 'colle:belhadi']);
  assert.equal(q.annee, 1876);
  assert.equal(q.tolerance, 3);
  const bad = parseQuery({ texte: 'Ali 1876 B.', annee: 'vers 1876', tolerance: -2 });
  assert.equal(bad.annee, null);
  assert.equal(bad.tolerance, DEFAULT_TOLERANCE);
  assert.deepEqual(bad.avertissements.map((a) => a.code).sort(), ['annee-illisible', 'nombre-ignore', 'tolerance-illisible']);
});

// ---------------------------------------------------------------------------------------------
// Pairs: one written name, one query -> class (or null when it must not come back)
// ---------------------------------------------------------------------------------------------
const PAIRS = [
  // written name, query, expected class
  ['Testaoui, Belkacem ben Chabane', 'Belkacem ben Chabane Testaoui', A],
  ['Testaoui, Belkacem ben Chabane', 'testaoui chabane belkacem', A], // free order, case
  ['Testaoui, Belkacem ben Chabane', 'Belkacem Chabane', A], // "ben" not required in the query
  ['Testaoui, Belkacem Chabane', 'Belkacem ben Chabane', A], // nor in the source
  ['TESTAOUI, Belkassem ben Chaabane', 'Belkacem ben Chabane', A], // k1
  ['Testaoui, Bel Kaçem ben Châbane', 'Belkacem Chabane', A], // split in the source, accents, cedilla
  ['Testaoui, Belkacem', 'Bel Kacem', A], // split in the query
  ['Testaoui, Mohamed ben Chabane', 'Benchabane Mohamed', A], // glued in the query, split in the source: spacing only
  ['Testaoui, Mohamed Chabane', 'Benchabane Mohamed', B], // no "ben" in the source: prefix detached from the query
  ['Benchabane, Mohamed', 'ben Chabane Mohamed', A], // typed split, written glued: spacing only
  ['Benchabane, Mohamed', 'Chabane Mohamed', B], // prefix detached from the written word
  ['Ezzemri, Djilali', 'Zemri Djilali', B],
  ['Zemri, Djilali', 'Ezzemri Djilali', B],
  ['Bouchabane, Ali', 'Benchabane Ali', C], // one detachment at most: never prefix-to-prefix
  ['Belhadi, Amar', 'Bel Hadi Amar', A],
  ['Bel Hadi, Amar', 'Belhadi Amar', A],
  ['Testaoui, Belgacem', 'Belkacem Testaoui', B], // k2
  ['Testaoui, Bel Gassem', 'Belkacem Testaoui', B], // k2 on a form glued by us
  ['Testaoui, M\'hamed', 'Mohamed Testaoui', B],
  ['Testaoui, Mahmoud', 'Mohamed Testaoui', B], // documented collision, shown as approximate
  ['Testaoui, Mohand', 'Mohamed Testaoui', C], // not the same word at any level: partial
  ['Testaoui, Mohand', 'Mohamed', null],
  ['Abd el Kader ben Ali', 'Abdelkader Ali', A],
  ['Abdelkader ben Ali', 'Abd-el-Kader Ali', A],
  ['Abdelkader ben Ali', 'Kader Ali', B],
  // Particles: never required, never searched
  ['El Hadj Ahmed ben Ali', 'Belhadj', null], // "Belhadj" must not match every "El Hadj"
  ['Testaoui, Ali bel Hadj', 'Belhadj Ali', A],
  ['Belhadj, Ali', 'Belhadi Ali', C], // Belhadi != Belhadj
  ['Belhadj, Ali', 'Belhadi', null],
  ['El Hadj Ahmed ben Ali', 'Hadj Ahmed', A], // "Hadj" ignored, Ahmed found
  ['Mohamed ben Ali', '"Hadj" Mohamed', C], // forced particle is required
  ['El Hadj Mohamed ben Ali', '"Hadj" Mohamed', A],
  ['Testaoui, Ali bel Hadj', '"Bel Hadj" Ali', A], // a forced compound, written in two words in the source
  ['Benchabane, Ali', '"Chabane" Ali', C], // a forced word is not looked for behind a prefix
  ['Testaoui, Benn', 'ben Testaoui', A],
  ['Mohamed ben Ali', 'Benn', null], // a word that merely looks like a particle never matches particles
  ['Testaoui née Exemplaoui, Fatma bent Ali', 'Fatma Exemplaoui', A],
  ['Testaoui veuve Fictifi, Aïcha', 'Aicha Fictifi', A],
  // Guards of the approximate level
  ['Testaoui, Saad', 'Saïd Testaoui', C], // too short for k2
  ['Testaoui, Saad', 'Saïd', null],
  ['Bonelli, Fictif', 'ben Ali Fictif', C], // "ben Ali" glued must not be an approximate "Bonelli"
  ['Mohamed ben Ali', 'Bonelli Mohamed', C], // nor the reverse
  ['Belgacem ben Ali', 'Kassem Ali', C], // approximate + detached prefix are never combined
  ['Testaoui, Kassem', 'Belgacem Testaoui', C],
  ['Testaoui, Ali', 'Testaoui', A],
  ['Testaoui, Ali', 'Exemplaoui', null],
  // Two terms need two written words
  ['Testaoui, Mohamed', 'Mohamed ben Mohamed', C],
  ['Mohamed ben Mohamed Testaoui', 'Mohamed ben Mohamed', A],
  ['Fictif ben Fictif', 'Fictif Fictif', A],
  // European particles and elision
  ['De Exemplo, Jean', 'Deexemplo Jean', A],
  ["D'Exemplo, Jean", 'Exemplo Jean', B],
  ['Diexemplo, Jean', 'Di Exemplo Jean', A],
];
for (const [name, query, expected] of PAIRS) {
  test(`« ${name} » for query « ${query} » -> ${expected ?? 'nothing'}`, () => {
    assert.equal(classOf(name, query), expected);
  });
}

// OCR-damaged printed forms: only in a printed group
const OCR_PAIRS = [
  ['Ali bon Slimane', 'Benslimane Ali', A],
  ['Ali ban Slimane', 'Ali ben Slimane', A],
  ['Mohamed ten Larbi ben bel Kaçem', 'Belkacem Larbi Mohamed', A],
  ['Aliben Fictifi', 'Ali Fictifi', B], // "ben" glued to the end of Ali
  ['Aliben Fictifi', 'Ali ben Fictifi', B],
  ['Rabah-ben-Mohamedben-Exemple', 'Mohamed Rabah Exemple', B],
  ['Moh:mmed ben Ali', 'Mohamed Ali', B], // sign inside the word dropped, then skeleton
  ['Mohammed ben Larbi, indigène', 'Larbi Mohamed', A],
];
for (const [name, query, expected] of OCR_PAIRS) {
  test(`printed « ${name} » for query « ${query} » -> ${expected}`, () => {
    const index = indexOf([[name, null, 'bogga']]);
    const { correspondances } = search(index, query);
    assert.equal(correspondances.length === 0 ? null : correspondances[0].classe, expected);
  });
}

test('OCR "bon" is a particle only in a printed source', () => {
  assert.equal(classOf('Ali bon Slimane', 'Benslimane Ali'), B, 'archival source: "bon" is a word, the prefix is detached');
  const printed = indexOf([['Ali bon Slimane', null, 'bogga']]);
  assert.equal(search(printed, 'Bon').correspondances.length, 0, 'the OCR particle is not a name');
  const surname = indexOf([['Bon, Ali', null, 'bogga']]);
  assert.equal(search(surname, 'Bon').correspondances.length, 1, 'a capitalised first word stays a name');
});

// ---------------------------------------------------------------------------------------------
// Explanations
// ---------------------------------------------------------------------------------------------
const INDEX = indexOf([
  ['Testaoui, Belkacem ben Chabane', 1876],
  ['TESTAOUI, Belgacem ben Chaabane', 1879],
  ['Bel Kaçem ben Châbane Testaoui', null, 'bogga'],
  ['Testaoui, Mohamed ben Chabane', 1877],
  ['Benchabane, Belkacem', 1860],
  ['Testaoui, Belkacem ben Chabane', 1890],
  ['Exemplaoui, Belkassem ben Chabane', 1874],
  ['Fictifi, Kacem ben Ali', 1876],
]);

test('each result explains every term: written word, level, gluing', () => {
  const { correspondances } = search(INDEX, 'Testaoui Belkacem ben Chabane');
  const byName = (nom) => correspondances.find((r) => r.nom === nom);

  const exact = byName('Testaoui, Belkacem ben Chabane');
  assert.equal(exact.classe, A);
  assert.deepEqual(exact.termes.map((t) => [t.terme, t.ecrit, t.niveau, t.soudure, t.exact]), [
    ['Testaoui', 'Testaoui', 'k0', null, true], ['Belkacem', 'Belkacem', 'k0', null, true], ['Chabane', 'Chabane', 'k0', null, true],
  ]);
  assert.equal(exact.termesExacts, 3);
  assert.equal(exact.termeAbsent, null);

  const approx = byName('TESTAOUI, Belgacem ben Chaabane');
  assert.equal(approx.classe, B);
  assert.deepEqual(approx.termes.map((t) => [t.terme, t.ecrit, t.niveau]), [
    ['Testaoui', 'TESTAOUI', 'k0'], ['Belkacem', 'Belgacem', 'k2'], ['Chabane', 'Chaabane', 'k1'],
  ]);
  assert.equal(approx.termesExacts, 1);

  const split = byName('Bel Kaçem ben Châbane Testaoui');
  assert.equal(split.classe, A);
  const bk = split.termes[1];
  assert.deepEqual([bk.ecrit, bk.niveau, bk.soudure, bk.prefixe, bk.position], ['Bel Kaçem', 'k0', 'colle', 'bel', 1]);
  assert.equal(split.groupe, 'bogga');

  const partial = byName('Testaoui, Mohamed ben Chabane');
  assert.equal(partial.classe, C);
  assert.equal(partial.termeAbsent, 'Belkacem');
  assert.deepEqual(partial.termes[1], { terme: 'Belkacem', absent: true });
});

test('a detached prefix is named, on whichever side it was', () => {
  const src = search(INDEX, 'Chabane Belkacem').correspondances.find((r) => r.nom === 'Benchabane, Belkacem');
  assert.equal(src.classe, B);
  assert.deepEqual([src.termes[0].ecrit, src.termes[0].soudure, src.termes[0].prefixe], ['Benchabane', 'prefixe-source', 'ben']);
  const typed = search(INDEX, 'Belkacem Ali').correspondances.find((r) => r.nom === 'Fictifi, Kacem ben Ali');
  assert.equal(typed.classe, B);
  assert.deepEqual([typed.termes[0].ecrit, typed.termes[0].soudure, typed.termes[0].prefixe], ['Kacem', 'prefixe-saisie', 'bel']);
});

test('user variants: the variant that matched is reported', () => {
  const { correspondances } = search(INDEX, 'Belkacem|Belgacem Testaoui');
  const r = correspondances.find((x) => x.nom === 'TESTAOUI, Belgacem ben Chaabane');
  assert.equal(r.classe, A, 'a spelling typed as a variant is no longer approximate');
  assert.equal(r.termes[0].variante, 'Belgacem');
  assert.equal(r.termes[0].terme, 'Belkacem');
});

test('unticking a spelling removes it, also when reached through a prefix', () => {
  const before = classes(INDEX, 'Belkacem Chabane');
  assert.ok(before[B].includes('TESTAOUI, Belgacem ben Chaabane'));
  assert.ok(before[B].includes('Benchabane, Belkacem'));
  const after = classes(INDEX, { termes: [{ variantes: ['Belkacem'], exclues: ['Belgacem'] }, { variantes: ['Chabane'], exclues: ['Benchabane'] }] });
  assert.ok(!after[B].includes('TESTAOUI, Belgacem ben Chaabane'));
  assert.ok(!after[B].includes('Benchabane, Belkacem'));
  assert.ok(!after[A].includes('Benchabane, Belkacem'));
  const text = classes(INDEX, 'Belkacem|-Belgacem Chabane');
  assert.ok(!text[B].includes('TESTAOUI, Belgacem ben Chaabane'));
});

// ---------------------------------------------------------------------------------------------
// Partial correspondences
// ---------------------------------------------------------------------------------------------
test('partial: exactly one term missing, never two, never with one term', () => {
  const c = classes(INDEX, 'Testaoui Belkacem ben Chabane');
  assert.deepEqual(c[C].sort(), ['Benchabane, Belkacem', 'Exemplaoui, Belkassem ben Chabane', 'Testaoui, Mohamed ben Chabane'].sort());
  assert.ok(!c[C].includes('Fictifi, Kacem ben Ali'), 'two terms missing is not a correspondence');
  assert.deepEqual(classes(INDEX, 'Exemplaoui')[C], []);
  assert.deepEqual(classes(INDEX, 'Introuvable')[A], []);
});

test('partial: the terms that are present must be found at k0/k1, never approximately', () => {
  const index = indexOf([['Fictifi, Belgacem ben Chabane', 1870], ['Fictifi, Belkacem ben Chabane', 1870]]);
  const c = classes(index, 'Testaoui Belkacem Chabane');
  assert.deepEqual(c[C], ['Fictifi, Belkacem ben Chabane']);
});

test('partial correspondences can be switched off', () => {
  const c = classes(INDEX, 'Testaoui Belkacem ben Chabane', { partielles: false });
  assert.deepEqual(c[C], []);
});

test('a result is in one class only, the best one', () => {
  const { correspondances } = search(INDEX, 'Testaoui Belkacem ben Chabane');
  const names = correspondances.map((r) => `${r.id}`);
  assert.equal(new Set(names).size, names.length);
});

// ---------------------------------------------------------------------------------------------
// Birth year
// ---------------------------------------------------------------------------------------------
test('birth year: default tolerance of 5 years, unknown years kept and labelled', () => {
  const { correspondances, bilan } = search(INDEX, { texte: 'Testaoui Belkacem ben Chabane', annee: 1876 });
  assert.deepEqual(bilan.annee, { valeur: 1876, tolerance: 5, de: 1871, a: 1881 });
  const names = correspondances.map((r) => `${r.nom} ${r.anneeNaissance}`);
  assert.ok(names.includes('Testaoui, Belkacem ben Chabane 1876'));
  assert.ok(!names.includes('Testaoui, Belkacem ben Chabane 1890'), '1890 is outside 1871-1881');
  const unknown = correspondances.find((r) => r.anneeNaissance === null);
  assert.deepEqual(unknown.annee, { ecart: null, inconnue: true });
  assert.deepEqual(correspondances[0].annee, { ecart: 0, inconnue: false });
  assert.equal(correspondances.find((r) => r.anneeNaissance === 1879).annee.ecart, 3);
  assert.equal(bilan.comptes.ecarteesParAnnee.correspondance, 1);
  assert.equal(bilan.comptes.ecarteesParAnnee.partielle, 1, 'Benchabane, Belkacem (1860)');
  assert.equal(bilan.comptes.sansAnneeDeNaissance, 1);
});

test('birth year: the tolerance can be changed, down to zero', () => {
  const wide = search(INDEX, { texte: 'Testaoui Belkacem Chabane', annee: 1876, tolerance: 14 });
  assert.ok(wide.correspondances.some((r) => r.anneeNaissance === 1890));
  const strict = search(INDEX, { texte: 'Testaoui Belkacem Chabane', annee: 1876, tolerance: 0 });
  assert.deepEqual(strict.correspondances.filter((r) => r.classe === A).map((r) => r.anneeNaissance), [1876, null]);
});

test('without a birth year nothing is filtered', () => {
  const { correspondances, bilan } = search(INDEX, 'Testaoui Belkacem Chabane');
  assert.equal(bilan.annee, null);
  assert.equal(correspondances[0].annee, null);
  assert.ok(correspondances.some((r) => r.anneeNaissance === 1890));
});

// ---------------------------------------------------------------------------------------------
// Ordering
// ---------------------------------------------------------------------------------------------
test('order: class, then distance to the birth year, then exact terms, then source order', () => {
  const index = indexOf([
    ['Testaoui, Belkassem', 1880], // A, distance 4, 1 exact
    ['Testaoui, Belkacem', 1880], // A, distance 4, 2 exact
    ['Testaoui, Belgacem', 1876], // B, distance 0
    ['Testaoui, Belkacem', null], // A, unknown year
    ['Testaoui, Belkacem', 1877], // A, distance 1
    ['TESTAOUI, Belkacem', 1875], // A, distance 1 (source order after the previous one)
    ['Testaoui, Ali', 1876], // C
  ]);
  const { correspondances } = search(index, { texte: 'Testaoui Belkacem', annee: 1876 });
  assert.deepEqual(correspondances.map((r) => r.id), ['t5', 't6', 't2', 't1', 't4', 't3', 't7']);
  assert.deepEqual(correspondances.map((r) => r.classe), [A, A, A, A, A, B, C]);
});

test('order is stable: same query, same order; inserting unrelated names changes nothing', () => {
  const rows = [];
  for (let i = 0; i < 40; i++) rows.push([`Testaoui, Belkacem ben ${i % 2 ? 'Chabane' : 'Chaabane'}`, 1870 + (i % 7)]);
  const first = search(indexOf(rows), { texte: 'Testaoui Belkacem Chabane', annee: 1873 }).correspondances.map((r) => r.nom + r.anneeNaissance);
  const second = search(indexOf(rows), { texte: 'Testaoui Belkacem Chabane', annee: 1873 }).correspondances.map((r) => r.nom + r.anneeNaissance);
  assert.deepEqual(first, second);
  const padded = [];
  for (const row of rows) padded.push(['Fictifi, Jean', 1850], row);
  const third = search(indexOf(padded), { texte: 'Testaoui Belkacem Chabane', annee: 1873 }).correspondances.map((r) => r.nom + r.anneeNaissance);
  assert.deepEqual(first, third);
});

test('the same search can be repeated on one index (no state leaks between searches)', () => {
  const a = search(INDEX, 'Testaoui Belkacem ben Chabane').correspondances.map((r) => r.id + r.classe);
  search(INDEX, 'Mohamed');
  search(INDEX, 'Fictifi Kacem Ali');
  const b = search(INDEX, 'Testaoui Belkacem ben Chabane').correspondances.map((r) => r.id + r.classe);
  assert.deepEqual(a, b);
});

// ---------------------------------------------------------------------------------------------
// Bilan
// ---------------------------------------------------------------------------------------------
test('bilan: what was understood, what was applied, counts per class and per source', () => {
  const { bilan } = search(INDEX, { texte: 'Testaoui Belkacem ben Chabane', annee: 1876 });
  assert.equal(bilan.saisie, 'Testaoui Belkacem ben Chabane');
  assert.deepEqual(bilan.termes.map((t) => t.saisie), ['Testaoui', 'Belkacem', 'Chabane']);
  const belkacem = bilan.termes[1].variantes[0];
  assert.equal(belkacem.ecriture, 'latin');
  assert.deepEqual(belkacem.formes[0], { forme: 'belkacem', genre: 'entier', prefixe: null, k0: 'belkacem', k1: 'belkasem', k2: 'blksm' });
  assert.deepEqual(bilan.particulesIgnorees, [{ saisie: 'ben', particule: 'ben' }]);
  assert.deepEqual(bilan.comptes.parClasse, { correspondance: 2, 'graphie-approchante': 1, partielle: 2 });
  assert.deepEqual(bilan.comptes.parGroupe.bogga, { correspondance: 1, 'graphie-approchante': 0, partielle: 0 });
  assert.equal(bilan.comptes.total, 5);
  assert.deepEqual(Object.keys(bilan.comptes.parClasse), CLASSES);
  assert.deepEqual(bilan.index.parGroupe, { an: 7, bogga: 1 });
  assert.deepEqual(bilan.index.groupesOcr, ['bogga']);
  assert.deepEqual(bilan.regles.niveaux, ['k0', 'k1', 'k2']);
  assert.ok(bilan.regles.particules.includes('ben'));
  assert.equal(typeof bilan.dureeMs, 'number');
  const found = bilan.graphiesTrouvees[1];
  assert.equal(found.terme, 'Belkacem');
  assert.deepEqual(found.graphies.map((g) => [g.graphie, g.niveau, g.soudure, g.occurrences]), [
    ['Belkacem', 'k0', null, 3], ['Bel Kaçem', 'k0', 'colle', 1], ['Belkassem', 'k1', null, 1],
    ['Kacem', 'k0', 'prefixe-saisie', 1], ['Kaçem', 'k0', 'prefixe-saisie', 1], ['Belgacem', 'k2', null, 1],
  ]);
});

test('bilan when nothing is found: still complete, with zero counts', () => {
  const { correspondances, bilan } = search(INDEX, 'Introuvable Inconnu');
  assert.deepEqual(correspondances, []);
  assert.deepEqual(bilan.comptes.parClasse, { correspondance: 0, 'graphie-approchante': 0, partielle: 0 });
  assert.equal(bilan.termes.length, 2);
  assert.deepEqual(bilan.graphiesTrouvees.map((g) => g.nombre), [0, 0]);
  assert.equal(bilan.index.occurrences, 8);
});

test('empty or particle-only input returns nothing and says why', () => {
  for (const text of ['', '   ', 'ben', 'el hadj', '1876']) {
    const { correspondances, bilan } = search(INDEX, text);
    assert.deepEqual(correspondances, []);
    assert.ok(bilan.avertissements.some((a) => a.code === 'aucun-terme'), text);
  }
});

test('limit per class: counts stay complete, the list is cut and flagged', () => {
  const rows = [];
  for (let i = 0; i < 30; i++) rows.push([`Testaoui, Ali ben Exemple${i}`, 1850]);
  const { correspondances, bilan } = search(indexOf(rows), 'Testaoui Ali', { limite: 10 });
  assert.equal(correspondances.length, 10);
  assert.equal(bilan.comptes.parClasse.correspondance, 30);
  assert.equal(bilan.tronque.correspondance, true);
  assert.equal(bilan.limiteParClasse, 10);
});

test('the occurrence given at build time comes back with the result', () => {
  const { correspondances } = search(INDEX, 'Fictifi Kacem');
  assert.equal(correspondances[0].occurrence.id, 't8');
  assert.equal(correspondances[0].id, 't8');
});
