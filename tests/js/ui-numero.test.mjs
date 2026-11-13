import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { classerSaisie, situerDate } from '../../site/js/logique/numero.js';

const codes = (texte) => classerSaisie(texte).formes.map((f) => f.code);
const valeurs = (texte) => classerSaisie(texte).formes.map((f) => f.valeur);

test('numéro: an empty entry is said empty', () => {
  assert.equal(classerSaisie('').bilan, 'vide');
  assert.equal(classerSaisie('   ').vide, true);
});

test('numéro: a bare number is set apart, whatever its separators', () => {
  for (const s of ['262-1412', '2621412', '262/1412', '262 1412']) {
    const r = classerSaisie(s);
    assert.deepEqual(codes(s), ['nombre-nu'], s);
    assert.equal(r.bilan, 'numero-seul', s);
  }
});

test('numéro: a full citation has its three elements', () => {
  const r = classerSaisie('Décret du 12 mars 1903 — Bulletin officiel du Gouvernement général de l\'Algérie, 1903, p. 412.');
  assert.deepEqual(r.dates, ['1903-03-12']);
  assert.deepEqual(r.elements, { date: true, publication: true, pageOuDatePublication: true });
  assert.equal(r.bilan, 'complete');
});

test('numéro: dates are read in the usual French forms, and impossible dates are not dates', () => {
  assert.deepEqual(classerSaisie('12/03/1903').dates, ['1903-03-12']);
  assert.deepEqual(classerSaisie('12.3.1903').dates, ['1903-03-12']);
  assert.deepEqual(classerSaisie('1903-03-12').dates, ['1903-03-12']);
  assert.deepEqual(classerSaisie('le 1er août 1905').dates, ['1905-08-01']);
  assert.deepEqual(classerSaisie('3 fevrier 1935').dates, ['1935-02-03']);
  assert.deepEqual(classerSaisie('31/02/1903').dates, []);
  assert.equal(classerSaisie('12/03/1903').bilan, 'date-sans-publication');
});

test('numéro: file numbers, call numbers, documents, articles, pages, inventories', () => {
  assert.deepEqual(codes('1234 X 85'), ['dossier']);
  assert.deepEqual(valeurs('1234x85'), ['1234 X 85']);
  assert.deepEqual(codes('BB/34/438 document 21'), ['cote-bb34', 'document']);
  assert.deepEqual(valeurs('BB 34 438'), ['BB/34/438']);
  assert.deepEqual(codes('BB/11/1234'), ['cote-bb11']);
  assert.deepEqual(codes('BB/12/77'), ['cote-autre']);
  assert.deepEqual(codes('N° 350'), ['article']);
  assert.deepEqual(codes('page 34'), ['page']);
  assert.deepEqual(codes('FRAN_IR_057268'), ['inventaire']);
  assert.deepEqual(codes('Journal officiel'), ['publication']);
  assert.deepEqual(codes('JO'), ['publication']);
  assert.deepEqual(codes('1905'), ['annee']);
});

test('numéro: a mixed entry is read form by form, in the order of the text', () => {
  const r = classerSaisie('décret n° 262 du 1er avril 1905 JO page 34, réf. 4521');
  assert.deepEqual(r.formes.map((f) => f.code), ['article', 'date', 'publication', 'page', 'nombre-nu']);
  assert.equal(r.bilan, 'complete');
});

test('numéro: letters alone give no form, and the entry is bounded', () => {
  assert.deepEqual(codes('une référence de mon grand-père'), []);
  assert.equal(classerSaisie('une référence').bilan, 'autre');
  assert.ok(classerSaisie('1'.repeat(5000)).formes.length <= 1);
});

test('numéro: a date is placed against the collections of the site', () => {
  const bornes = { an: { de: 1883, a: 1948 }, bulletin: { de: 1861, a: 1888 } };
  assert.deepEqual(situerDate('1885-03-10', bornes), { annee: 1885, dansAn: true, dansBulletin: true });
  assert.deepEqual(situerDate('1870-01-01', bornes), { annee: 1870, dansAn: false, dansBulletin: true });
  assert.deepEqual(situerDate('1955-01-01', bornes), { annee: 1955, dansAn: false, dansBulletin: false });
});

test('numéro: the page relies on the texts of guide « numero-a-verifier » in the order it expects', () => {
  const guides = JSON.parse(readFileSync(new URL('../../site/contenu/guides.json', import.meta.url), 'utf8'));
  const g = guides.guides.find((x) => x.id === 'numero-a-verifier');
  const [k1, k2, k3, k4] = g.etapes;
  assert.deepEqual([k1.id, k2.id, k3.id, k4.id], ['k1', 'k2', 'k3', 'k4']);
  // k1: three elements / a date without publication / a number only
  assert.equal(k1.issues_possibles.length, 3);
  assert.match(k1.issues_possibles[2].si, /numéro/);
  // k2: found and the name is there / found, name not there / no decree that day / out of the collection
  assert.equal(k2.issues_possibles.length, 4);
  assert.match(k2.issues_possibles[2].si, /Aucun décret/);
  assert.match(k2.issues_possibles[3].si, /1883/);
  assert.match(k3.instruction, /numéro/);
  assert.ok(k4.instruction.length > 50);
});
