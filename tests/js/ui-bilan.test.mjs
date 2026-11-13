import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { cleDuResume, composerBilan, enoncerPeriodes, variablesDuBilan } from '../../site/js/logique/bilan.js';
import { creerModele } from '../../site/js/donnees/modele.js';
import { buildIndex, occurrencesFromColumns } from '../../site/js/recherche/index.js';
import { search } from '../../site/js/recherche/chercher.js';
import { fichiers } from './ui-aide.mjs';

const plat = (s) => s.replace(/[  ]/g, ' ');
const data = fichiers();
const couverture = creerModele(data).couverture();
const index = buildIndex([
  ...occurrencesFromColumns(data.anPersonnes, { groupe: 'an' }).occurrences,
  ...occurrencesFromColumns(data.boggaEntrees, { groupe: 'bogga', ocr: true }).occurrences,
], { groupesOcr: ['bogga'] });
// The real texts of the site (they hold no personal data).
const contenu = JSON.parse(readFileSync(new URL('../../site/contenu/bilan.json', import.meta.url), 'utf8'));

function bilanDe(texte, annee = null) {
  const etat = { texte, annee, tolerance: null, exclusions: {}, ajouts: {} };
  const { bilan } = search(index, annee === null ? { texte } : { texte, annee });
  return composerBilan({ bilanMoteur: bilan, couverture, contenu, etat, ageMinimal: 21 });
}

test('bilan: periods are said from the coverage tables, quarters included', () => {
  const { annees, trimestres } = couverture.an;
  assert.equal(enoncerPeriodes(annees, trimestres, (y) => y.lecture === 'lue'), '1885 et 1913');
  assert.equal(enoncerPeriodes(annees, trimestres, (y) => y.lecture === 'image' || y.lecture === 'image-en-partie'), '1899, 1900, avril à décembre 1928, 1933 et 1934');
  assert.equal(enoncerPeriodes(annees, trimestres, (y) => y.lecture === 'noms-aux-an'), '1898 et janvier à mars 1928');
  assert.equal(enoncerPeriodes([], [], () => true), '');
});

test('bilan: which summary applies', () => {
  assert.equal(cleDuResume({ correspondance: 1 }), 'une_correspondance');
  assert.equal(cleDuResume({ correspondance: 1, 'graphie-approchante': 2 }), 'plusieurs_correspondances');
  assert.equal(cleDuResume({ partielle: 4 }), 'partielles_seulement');
  assert.equal(cleDuResume({}), 'aucune');
  assert.equal(cleDuResume(undefined), 'aucune');
});

test('bilan: nothing found — the whole sentence of the content file, the sources, and what is not covered', () => {
  const b = bilanDe('Introuvablaoui Mokhtar', 1876);
  assert.equal(b.cleResume, 'aucune');
  assert.equal(b.resume, contenu.resume.aucune);
  // never a verdict on the person
  assert.doesNotMatch(b.resume, /n'a pas été admis|n'était pas français/);
  const an = b.fouille.lignes.find((l) => l.id === 'an-index');
  assert.match(plat(an.texte), /pour les années 1885 et 1913 \(inventaires relevés le 16 octobre 2026\)/);
  assert.match(plat(an.precisions[0]), /^6 noms lus dans cet index : les personnes des décrets, mais aussi 1 épouse et 2 enfants cités/);   // counted by the index and the meta file
  const bulletin = b.fouille.lignes.find((l) => l.id === 'bulletin');
  assert.match(plat(bulletin.texte), /pour les années 1861, 1873 et 1885\./);
  // the engine kept the notices born 1871-1881 (five years either way): the window starts at 1871 + 21
  assert.match(plat(b.fouille.lignes.find((l) => l.id === 'fenetre-naissance').texte), /1876, à 5 ans près.*1892/);
  assert.deepEqual(b.nonCouvert.lignes.map((l) => l.id), contenu.ce_qui_n_est_pas_couvert.lignes.map((l) => l.id));
  assert.match(plat(b.nonCouvert.lignes[0].titre), /1899, 1900, avril à décembre 1928, 1933 et 1934/);
  assert.doesNotMatch(JSON.stringify(b.nonCouvert.lignes), /\{[a-z_]+\}/, 'no template variable is left unfilled');
  assert.equal(b.nonCouvert.pagesALireALaMain.length, 1);
  assert.ok(b.rappelJugement.texte.length > 50, 'the reminder about judgments is in every bilan');
  assert.deepEqual(b.conseils.fenetre, { de: 1892, a: 1934 });
  assert.equal(b.conseils.tolerance, 5);
});

test('bilan: without a birth year the line about the year is left out and nothing is tailored', () => {
  const b = bilanDe('Introuvablaoui Mokhtar');
  assert.equal(b.fouille.lignes.some((l) => l.id === 'fenetre-naissance'), false);
  assert.equal(b.conseils.naissance, null);
  assert.equal(b.regles.some((r) => /Aucune année de naissance/.test(r)), true);
});

test('bilan: found — the rules really applied come from the engine, and the reminder about judgments stays', () => {
  const b = bilanDe('Belkacem ben Exemplane Testaoui', 1850);
  assert.equal(b.cleResume, 'une_correspondance');
  assert.match(plat(b.resume), /^Une correspondance pour « Belkacem », « Exemplane », « Testaoui »/);
  assert.equal(b.regles.some((r) => /Particules non exigées : ben/.test(plat(r))), true);
  assert.equal(b.regles.some((r) => /Année de naissance 1850, à 5 ans près/.test(plat(r))), true);
  assert.deepEqual(b.parSource.map((s) => [s.groupe, s.correspondance]), [['an', 1], ['bogga', 0]]);
  assert.ok(b.rappelJugement);
  assert.equal(b.graphies.length, 3);
});

test('bilan: the variables of the content file are all given a value from the data or the search', () => {
  const { bilan } = search(index, { texte: 'Belkacem|Belgacem Exemplane', annee: 1850 });
  const v = variablesDuBilan({ bilanMoteur: bilan, couverture, etat: { texte: 'Belkacem|Belgacem Exemplane', annee: 1850 } });
  for (const name of Object.keys(contenu.variables)) {
    if (name === 'terme_absent' || name === 'annee_min') continue; // per card, and set by the caller
    assert.ok(name in v, name);
    assert.notEqual(v[name], undefined, name);
  }
  assert.equal(v.nb_variantes, 3);
  assert.equal(v.annee_naissance, 1850);
});
