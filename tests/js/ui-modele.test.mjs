import { test } from 'node:test';
import assert from 'node:assert/strict';

import { creerModele, lecteurColonnes, lectureAnnee } from '../../site/js/donnees/modele.js';
import { fichiers } from './ui-aide.mjs';

const modele = creerModele(fichiers());

test('columns: a field named like a table is an index into it; a missing value is null', () => {
  const L = lecteurColonnes({ champs: ['id', 'role', 'nom'], tables: { role: ['principal', 'epouse'] }, lignes: [[0, 1, 'x'], [1, 0, null]] });
  assert.equal(L.valeur(0, 'role'), 'epouse');
  assert.equal(L.valeur(1, 'nom'), null);
  assert.equal(L.valeur(5, 'nom'), null);
  assert.equal(L.valeur(0, 'inconnu'), null);
  assert.equal(L.taille, 2);
  assert.throws(() => lecteurColonnes({ lignes: [] }), TypeError);
});

test('model: any row of a household gives the whole notice, principal first', () => {
  for (const ligne of [0, 1, 2, 3]) {
    const f = modele.ficheAn(ligne);
    assert.equal(f.cle, 'an:0');
    assert.deepEqual(f.membres.map((m) => m.role), ['principal', 'epouse', 'enfant', 'enfant']);
    assert.deepEqual(f.membres.map((m) => m.nom), ['Testaoui, Belkacem ben Exemplane', 'Exemplaoui, Fatma bent Ali', 'Ahmed', 'Zohra']);
  }
  assert.equal(modele.cleDe('an', 3), 'an:0');
  assert.equal(modele.cleDe('bogga', 3), 'bogga:3');
  assert.equal(modele.ficheAn(4).membres.length, 1);
  assert.equal(modele.ficheAn(99), null);
});

test('model: person -> decree -> coverage of the year; tables are resolved to their words', () => {
  const f = modele.ficheAn(0);
  assert.equal(f.decret.inv, 'FRAN_IR_000001');
  assert.equal(f.decret.notice, 'DEC001');
  assert.equal(f.decret.date, '1885-03-10');
  assert.equal(f.decret.famille, 'naturalisation');
  assert.equal(f.decret.classe, 'A1');
  assert.equal(f.decret.etat, 'indexe');
  assert.deepEqual(f.decret.couverture, { annee: 1885, trim: null, etat: 'indexe', lecture: 'lue', filae: false });
  assert.equal(f.membres[0].prec, 'conventionnelle');
  assert.equal(f.membres[2].prec, 'position');
  assert.equal(f.dossier, '1234 X 85');
  assert.equal(f.aSesImages, true);
  assert.deepEqual(f.ref, { source: 'an', inv: 'FRAN_IR_000001', notice: 'PERS001' });
});

test('model: the hint about a person is carried with its rule and its label, never as a fact', () => {
  const f = modele.ficheAn(0);
  assert.equal(f.indice.code, 'M');
  assert.match(f.indice.libelle, /probable/);
  assert.equal(f.indice.regle, 'ne-en-algerie(explicite)+filiation');
  assert.equal(f.neEnAlgerie, 'explicite');
  assert.equal(f.resideEnAlgerie, 'repertoire');
});

test('model: relatives withheld and mentions that are not names are counted, never named', () => {
  assert.equal(modele.ficheAn(5).prochesNonAffiches, 2);
  assert.equal(modele.ficheAn(0).mentionsNonNoms, 1);
  assert.equal(modele.ficheAn(4).prochesNonAffiches, 0);
});

test('model: an Archives nationales decree is joined to the Bulletin decrees printed with the same date', () => {
  const f = modele.ficheAn(0);
  assert.deepEqual(f.publications.map((p) => p.page), [120, 131]);
  assert.equal(f.publications[0].volume.annee, 1885);
  assert.equal(f.publications[0].livraisonDate, null);
  assert.equal(f.publications[1].doublonDe.page, 120);
  assert.deepEqual(modele.ficheAn(5).publications, []);
});

test('model: particular links — undefined follows the template, null means no link, a string is the source address', () => {
  assert.equal(modele.ficheAn(0).decret.lienImagesParticulier, undefined);
  assert.equal(modele.ficheAn(5).decret.lienImagesParticulier, null);
  assert.match(modele.decretsAn({ annees: [1933] })[0].lienImagesParticulier, /^http:\/\/www\.siv\.archives-nationales/);
  assert.equal(modele.ficheAn(5).decret.drapCote, 'suspecte-bb11');
  assert.equal(modele.ficheAn(5).decret.coteSuggeree, 'BB/34/901');
});

test('model: Bulletin entry -> decree as published -> volume, with labelled marks', () => {
  const f = modele.ficheBogga(0);
  assert.equal(f.cle, 'bogga:0');
  assert.equal(f.nom, 'Ali bon Slimane Exemplaoui');
  assert.equal(f.volume.annee, 1873);
  assert.equal(f.volume.item, 'bulletin_fictif_1873');
  assert.equal(f.decret.livraisonDate, '1873-12-06');
  assert.deepEqual(f.decret.dates, ['1873-11-05']);
  assert.deepEqual(f.marqueurs.map((m) => m.bit), [1]);
  assert.deepEqual(modele.ficheBogga(1).drapeaux.map((m) => m.bit), [64]);
  assert.equal(modele.ficheBogga(1).nationalite, 'suedois');
});

test('model: the reference kept in an address finds the same notice again', () => {
  for (const ligne of [0, 4, 5]) {
    const f = modele.ficheAn(ligne);
    assert.equal(modele.ficheParReference(f.ref).cle, f.cle);
  }
  // entries of one leaf that are not contiguous in the file still get distinct, stable ranks
  assert.deepEqual([0, 1, 3].map((l) => modele.ficheBogga(l).ref.rang), [0, 1, 2]);
  for (const ligne of [0, 1, 2, 3]) {
    const f = modele.ficheBogga(ligne);
    assert.equal(modele.ficheParReference(f.ref).cle, f.cle);
  }
  assert.equal(modele.ficheParReference({ source: 'an', inv: 'FRAN_IR_000001', notice: 'INCONNUE' }), null);
  assert.equal(modele.ficheParReference({ source: 'bogga', annee: 1873, feuille: 640, rang: 9 }), null);
  assert.equal(modele.ficheParReference({ source: 'autre' }), null);
  assert.equal(modele.fiche('an:1').cle, 'an:0');
  assert.equal(modele.fiche('n\'importe quoi'), null);
});

test('model: how a year can be searched from this site', () => {
  assert.equal(lectureAnnee({ etat: 'indexe', noms_exportes: true }), 'lue');
  assert.equal(lectureAnnee({ etat: 'partiel', noms_exportes: true }), 'lue-en-partie');
  assert.equal(lectureAnnee({ etat: 'indexe', noms_exportes: false }), 'noms-aux-an');
  assert.equal(lectureAnnee({ etat: 'partiel', noms_exportes: false }), 'image-en-partie');
  assert.equal(lectureAnnee({ etat: 'image', noms_exportes: false }), 'image');
});

test('model: the coverage summary comes from the meta files — counts, years, pages to read by hand', () => {
  const c = modele.couverture();
  assert.equal(c.an.noms, 6);
  assert.equal(c.an.releveLe, '2026-10-16');
  assert.deepEqual(c.an.annees.map((y) => [y.annee, y.lecture]), [[1885, 'lue'], [1898, 'noms-aux-an'], [1899, 'image'], [1900, 'image-en-partie'], [1913, 'lue'], [1928, 'image-en-partie'], [1933, 'image'], [1934, 'image']]);
  assert.deepEqual(c.an.annees.find((y) => y.annee === 1898).inventaires.map((i) => i.inv), ['FRAN_IR_000003']);
  assert.equal(c.an.trimestres.length, 4);
  assert.deepEqual(c.bogga.annees.map((y) => [y.annee, y.lu, y.decrets]), [[1861, true, 0], [1862, false, 0], [1873, true, 1], [1885, true, 2]]);
  assert.equal(c.bogga.pagesALireALaMain.length, 1);
  assert.equal(c.bogga.pagesALireALaMain[0].volume.item, 'bulletin_fictif_1873');
});

test('model: the decree browser can filter by year, class and state', () => {
  assert.deepEqual(modele.decretsAn({ annees: [1913, 1933] }).map((d) => d.notice), ['DEC002', 'DEC003']);
  assert.deepEqual(modele.decretsAn({ etats: ['image'] }).map((d) => d.notice), ['DEC003']);
  assert.deepEqual(modele.decretsAn({ classes: ['A1'], annees: [1885] }).map((d) => d.notice), ['DEC001']);
  assert.equal(modele.decretsAn().length, 3);
});
