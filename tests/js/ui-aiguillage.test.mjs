import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { cheminVers, epoquesPour, issueParId, issuesAtteignables, lireReponses, parcourir } from '../../site/js/logique/aiguillage.js';

// The real decision tree of the site (it holds no personal data).
const lire = (nom) => JSON.parse(readFileSync(new URL(`../../site/contenu/${nom}.json`, import.meta.url), 'utf8'));
const arbre = lire('aiguillage');
const types = new Set(lire('types-d-actes').types.map((t) => t.id));
const guides = new Set(lire('guides').guides.map((g) => g.id));
const liens = new Map(lire('liens').liens.map((l) => [l.id, l]));
const bilan = lire('bilan');

test('aiguillage: no answer yet -> the first question', () => {
  const r = parcourir(arbre, []);
  assert.equal(r.question.id, arbre.depart);
  assert.equal(r.issue, null);
  assert.deepEqual(r.chemin, []);
});

test('aiguillage: answers are followed to an outcome, with the trail kept', () => {
  const r = parcourir(arbre, ['d-ancetre', 'f-musulmane', 'i-rien']);
  assert.equal(r.question, null);
  assert.equal(r.issue.id, 'recherche-sans-indice');
  assert.deepEqual(r.chemin.map((c) => c.reponse.id), ['d-ancetre', 'f-musulmane', 'i-rien']);
  assert.deepEqual(r.ignorees, []);
});

test('aiguillage: one answer can lead straight to an outcome', () => {
  const r = parcourir(arbre, ['d-numero']);
  assert.equal(r.issue.id, 'numero-a-verifier');
});

test('aiguillage: an answer that does not fit stops the walk where it is, and is reported', () => {
  const r = parcourir(arbre, ['d-ancetre', 'inconnue', 'i-rien']);
  assert.equal(r.question.id, 'q-famille');
  assert.deepEqual(r.ignorees, ['inconnue', 'i-rien']);
  // answers after an outcome are ignored too
  const s = parcourir(arbre, ['d-numero', 'f-musulmane']);
  assert.equal(s.issue.id, 'numero-a-verifier');
  assert.deepEqual(s.ignorees, ['f-musulmane']);
});

test('aiguillage: reading the answers from an address keeps plausible ids only', () => {
  assert.deepEqual(lireReponses('d-ancetre, f-musulmane,,<script>,i-rien'), ['d-ancetre', 'f-musulmane', 'i-rien']);
  assert.deepEqual(lireReponses(undefined), []);
});

test('aiguillage: every outcome can be reached, in three questions at most, and every reference it makes resolves', () => {
  const atteintes = issuesAtteignables(arbre);
  assert.deepEqual(atteintes.sort(), arbre.issues.map((i) => i.id).sort(), 'every outcome is reachable');
  const voies = new Set(arbre.voies.map((v) => v.id));
  for (const issue of arbre.issues) {
    const chemin = cheminVers(arbre, issue.id);
    assert.ok(chemin && chemin.length <= 3, issue.id);
    assert.equal(parcourir(arbre, chemin).issue.id, issue.id);
    assert.equal(issueParId(arbre, issue.id), issue);
    assert.ok(voies.has(issue.voie), `${issue.id}: voie ${issue.voie}`);
    for (const v of issue.voies_secondaires) assert.ok(voies.has(v), `${issue.id}: voie ${v}`);
    for (const t of issue.types) assert.ok(types.has(t), `${issue.id}: type ${t}`);
    for (const g of issue.guides) assert.ok(guides.has(g), `${issue.id}: guide ${g}`);
    for (const l of issue.liens) assert.equal(liens.get(l)?.proposer, true, `${issue.id}: lien ${l}`);
    if (issue.rappel_jugement) assert.ok(bilan.rappel_jugement.court);
    if (issue.montrer_echelle) assert.ok(bilan.echelle.chiffres.length > 0);
  }
  for (const voie of arbre.voies) for (const g of voie.guides) assert.ok(guides.has(g), `voie ${voie.id}: guide ${g}`);
  for (const e of arbre.epoques) for (const g of e.guides) assert.ok(guides.has(g), `époque ${e.id}: guide ${g}`);
});

test('aiguillage: the periods shown for a birth year start at the year of the minimum age', () => {
  assert.equal(epoquesPour(arbre, null).length, arbre.epoques.length);
  const pour1900 = epoquesPour(arbre, 1900).map((e) => e.id);
  assert.ok(!pour1900.includes('e-1865-1882'));
  assert.ok(!pour1900.includes('e-1899-1912'), '1900 + 21 = 1921: 1899-1912 is over');
  assert.ok(pour1900.includes('e-1913-1927'));
  assert.ok(pour1900.includes('e-jugements'));
});
