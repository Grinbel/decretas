import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildIndex, occurrencesFromColumns, indexSummary, DataFormatError, writtenCount, displayForm } from '../../site/js/recherche/index.js';
import { search } from '../../site/js/recherche/chercher.js';

const DATA = {
  format: 'essai/1',
  champs: ['id', 'role', 'nom', 'an', 'conjoint'],
  lignes: [
    ['p1', 'principal', 'Testaoui, Belkacem ben Chabane', 1876, 'Exemplaoui, Fatma bent Ali'],
    ['p2', 'principal', 'TESTAOUI, Amar', null, null],
    ['p3', 'principal', '', 1880, null],
    ['p4', 'principal', 'Fictifi, Ali', '1881-03-02', ''],
  ],
};

test('columnar adapter: usual column names are detected', () => {
  const { occurrences, colonnes, lignes, sansNom } = occurrencesFromColumns(DATA, { groupe: 'an' });
  assert.deepEqual(colonnes, { nom: ['nom'], id: 'id', annee: 'an' });
  assert.equal(lignes, 4);
  assert.equal(sansNom, 1);
  assert.deepEqual(occurrences, [
    { id: 'p1', nom: 'Testaoui, Belkacem ben Chabane', anneeNaissance: 1876, groupe: 'an', ligne: 0 },
    { id: 'p2', nom: 'TESTAOUI, Amar', anneeNaissance: null, groupe: 'an', ligne: 1 },
    { id: 'p4', nom: 'Fictifi, Ali', anneeNaissance: 1881, groupe: 'an', ligne: 3 },
  ]);
});

test('columnar adapter: explicit columns, several name columns, row number as identifier', () => {
  const { occurrences, colonnes } = occurrencesFromColumns(
    { champs: ['texte', 'conjoint', 'ne'], lignes: [['Testaoui, Ali', 'Exemplaoui, Fatma', 1850], ['Fictifi, Amar', null, 'inconnue']] },
    { groupe: 'bogga', champNom: 'texte,conjoint', champAnnee: 'ne', ocr: true },
  );
  assert.deepEqual(colonnes, { nom: ['texte', 'conjoint'], id: null, annee: 'ne' });
  assert.deepEqual(occurrences.map((o) => [o.id, o.nom, o.champ, o.anneeNaissance, o.ocr]), [
    [0, 'Testaoui, Ali', 'texte', 1850, true], [0, 'Exemplaoui, Fatma', 'conjoint', 1850, true], [1, 'Fictifi, Amar', 'texte', null, true],
  ]);
});

test('columnar adapter: clear errors, in French', () => {
  assert.throws(() => occurrencesFromColumns([], { groupe: 'an' }), DataFormatError);
  assert.throws(() => occurrencesFromColumns({ champs: ['a'], lignes: 3 }, { groupe: 'an' }), /Format inattendu/);
  assert.throws(() => occurrencesFromColumns({ champs: ['a', 'b'], lignes: [] }, { groupe: 'an' }), /Aucune colonne reconnue pour le nom.*a, b/);
  assert.throws(() => occurrencesFromColumns(DATA, { groupe: 'an', champNom: 'patronyme' }), /Colonne « patronyme » absente/);
  assert.throws(() => occurrencesFromColumns({ champs: ['nom'], lignes: ['Testaoui'] }, { groupe: 'an' }), /Ligne 0/);
});

test('"annee" alone is not taken for a birth year', () => {
  const { colonnes } = occurrencesFromColumns({ champs: ['nom', 'annee'], lignes: [] }, { groupe: 'an' });
  assert.equal(colonnes.annee, null);
});

test('buildIndex: groups, years, summary', () => {
  const { occurrences } = occurrencesFromColumns(DATA, { groupe: 'an' });
  const printed = [{ id: 'b1', nom: 'Ali bon Slimane', anneeNaissance: 'vers 1850', groupe: 'bogga' }];
  const index = buildIndex(occurrences.concat(printed), { groupesOcr: ['bogga'] });
  const summary = indexSummary(index);
  assert.equal(summary.occurrences, 4);
  assert.deepEqual(summary.parGroupe, { an: 3, bogga: 1 });
  assert.deepEqual(summary.groupesOcr, ['bogga']);
  assert.ok(summary.formes > 5);
  assert.deepEqual([...index.years], [1876, 0, 1881, 0], 'an unreadable year is unknown, never guessed');
});

test('buildIndex: counts and display spellings of forms', () => {
  const index = buildIndex([
    { id: 1, nom: 'BELKACEM, Ali', anneeNaissance: null, groupe: 'an' },
    { id: 2, nom: 'Testaoui, Bel Kacem', anneeNaissance: null, groupe: 'an' },
    { id: 3, nom: 'Testaoui, Belkacem ben Belkacem', anneeNaissance: null, groupe: 'an' },
  ]);
  const fid = index.byCle.get('belkacem');
  assert.equal(writtenCount(index, fid), 3, 'occurrences, not words');
  assert.equal(displayForm(index, fid), 'Belkacem', 'capitals of the archive are not shouted back');
});

test('buildIndex: an empty index answers without failing', () => {
  const index = buildIndex([]);
  const { correspondances, bilan } = search(index, 'Testaoui');
  assert.deepEqual(correspondances, []);
  assert.equal(bilan.index.occurrences, 0);
});

test('buildIndex: odd names do not break it', () => {
  const long = Array.from({ length: 400 }, (_, i) => `Mot${i}`).join(' ');
  const index = buildIndex([
    { id: 1, nom: null, anneeNaissance: null, groupe: 'an' },
    { id: 2, nom: '— 495 —', anneeNaissance: null, groupe: 'an' },
    { id: 3, nom: long, anneeNaissance: 99999, groupe: 'an' },
    { id: 4, nom: 'Testaoui (rejet du 14 juillet 1865), Ali [Aly]', anneeNaissance: 1850, groupe: 'an' },
  ]);
  assert.equal(index.size, 4);
  assert.equal(search(index, 'Testaoui Aly').correspondances.length, 1);
  assert.equal(search(index, 'Motaaa').correspondances.length, 0);
});
