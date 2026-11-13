import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  GROUPES, anneesDisponibles, cleDecret, comptesParAnnee, comptesParGroupe, dejaLus, fenetreDemandee,
  filtrerDecrets, groupeDeLecture, lireGroupes, trierPourLecture,
} from '../../site/js/logique/decrets.js';

// Invented decrees, in the shape of donnees/modele.js#decretAn.
let n = 0;
const dec = (annee, classe, famille, date, doc = null) => ({ inv: 'FRAN_IR_000009', notice: `D${String(++n).padStart(3, '0')}`, annee, classe, famille, date, doc, etat: 'image' });
const decrets = [
  dec(1905, 'A1', 'naturalisation', '1905-03-01', 'document 9'),
  dec(1905, 'A1', 'naturalisation', '1905-03-01', 'document 2'),
  dec(1905, 'R', 'rejet', '1905-01-10'),
  dec(1905, 'A1', 'naturalisation', null),
  dec(1935, 'A1', 'naturalisation+reintegration', '1935-01-02'),
  dec(1935, 'A2', 'admission-citoyen', '1935-01-03'),
  dec(1935, 'A1', 'admission-citoyen', '1935-06-01'),
  dec(1944, 'A3', 'composite-avec-citoyen', '1944-03-30'),
  dec(1910, 'A1', 'admission-domicile', '1910-05-05'),
];

test('décrets: the reading group follows guide b2', () => {
  assert.equal(groupeDeLecture(decrets[0]), 'naturalisations-algeriennes');
  assert.equal(groupeDeLecture(decrets[2]), 'rejets');
  assert.equal(groupeDeLecture(decrets[4]), 'etrangers-algerie', 'from 1931 the « naturalisations françaises (Algérie) » are foreigners');
  assert.equal(groupeDeLecture(decrets[5]), 'admission-sans-territoire');
  assert.equal(groupeDeLecture(decrets[6]), 'admission-algerie');
  assert.equal(groupeDeLecture(decrets[7]), 'composites');
  assert.equal(groupeDeLecture(decrets[8]), 'etrangers-algerie');
  assert.equal(groupeDeLecture({ classe: '-', famille: 'divers', annee: 1920 }), 'autres');
});

test('décrets: sorted by year, reading group, date (undated last), then document number', () => {
  const tri = trierPourLecture(decrets).map((d) => d.notice);
  assert.deepEqual(tri, ['D002', 'D001', 'D004', 'D003', 'D009', 'D007', 'D006', 'D005', 'D008']);
});

test('décrets: available years, window from a birth year, explicit years from the bilan', () => {
  const dispo = anneesDisponibles(decrets);
  assert.deepEqual(dispo, [1905, 1910, 1935, 1944]);
  assert.deepEqual(fenetreDemandee({ naissance: 1886 }, dispo, 21), { de: 1907, a: 1944, annees: [1910, 1935, 1944], depuisNaissance: true });
  assert.deepEqual(fenetreDemandee({}, dispo, 21).annees, dispo);
  assert.deepEqual(fenetreDemandee({ annees: [1905, 1935] }, dispo, 21).annees, [1905, 1935]);
  assert.deepEqual(fenetreDemandee({ de: 1906, a: 1940, annees: [1905, 1935] }, dispo, 21).annees, [1910, 1935], 'a range typed by the user wins');
  assert.deepEqual(fenetreDemandee({ naissance: 1940 }, dispo, 21).annees, [], 'born too late for these years');
  assert.deepEqual(fenetreDemandee({}, [], 21).annees, []);
});

test('décrets: filter by years and groups, counts per year and per group', () => {
  const liste = filtrerDecrets(decrets, { annees: [1905, 1935], groupes: ['naturalisations-algeriennes', 'admission-algerie'] });
  assert.deepEqual(liste.map((d) => d.notice), ['D002', 'D001', 'D004', 'D007']);
  const parAnnee = comptesParAnnee(decrets);
  assert.equal(parAnnee.get(1905).total, 4);
  assert.equal(parAnnee.get(1905).groupes.rejets, 1);
  const parGroupe = comptesParGroupe(decrets);
  assert.equal(Object.values(parGroupe).reduce((a, b) => a + b, 0), decrets.length);
  assert.deepEqual(Object.keys(parGroupe), [...GROUPES]);
});

test('décrets: stable keys, read count, groups from an address', () => {
  assert.equal(cleDecret(decrets[0]), 'FRAN_IR_000009/D001');
  assert.equal(dejaLus(decrets, new Set(['FRAN_IR_000009/D001', 'FRAN_IR_000009/D999'])), 1);
  assert.deepEqual(lireGroupes('rejets,inconnu,composites'), ['rejets', 'composites']);
  assert.equal(lireGroupes('inconnu'), null);
  assert.equal(lireGroupes(undefined), null);
});
