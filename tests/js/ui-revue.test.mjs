/**
 * Regression tests for the review of 2026-11-12 (three reviewers of the built site). One test per
 * finding whose logic can be checked without a browser; the visual and interaction ones were
 * re-checked in Chromium (data/build/captures/, not committed). Every name below is invented.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { creerClientDonnees } from '../../site/js/donnees/client.js';
import { creerContenu } from '../../site/js/donnees/contenu.js';
import { creerModele, menageReconnu, motsDuMenage, natureCompatible } from '../../site/js/donnees/modele.js';
import { sansAnneesDouteuses } from '../../site/js/donnees/service.js';
import { conseilsPourAnnee, fenetreAdmission, nomsAuxAnSeulement } from '../../site/js/logique/fenetre-annees.js';
import { composerBilan, enoncerPeriodes, variablesDuBilan } from '../../site/js/logique/bilan.js';
import { fenetreDemandee } from '../../site/js/logique/decrets.js';
import { classerSaisie } from '../../site/js/logique/numero.js';
import { creerLiens } from '../../site/js/logique/liens.js';
import { avecPosition, fenetresSauvees, lirePosition } from '../../site/js/logique/position.js';
import { noteDeVerification } from '../../site/js/logique/verification.js';
import { saufTechniques, typographier, typographierTout } from '../../site/js/textes/typographie.js';
import { regleEnClair } from '../../site/js/composants/fiche.js';
import { messageDEchec } from '../../site/js/vues/recherche.js';
import { T } from '../../site/js/textes/index.js';
import { buildIndex, occurrencesFromColumns } from '../../site/js/recherche/index.js';
import { search } from '../../site/js/recherche/chercher.js';
import { fichiers, tableDeLiens } from './ui-aide.mjs';

const lire = (nom) => JSON.parse(readFileSync(new URL(`../../site/contenu/${nom}.json`, import.meta.url), 'utf8'));
const plat = (s) => String(s).replace(/[  ]/g, ' ');

// ----- the data client: a failed download is never kept ----------------------------------------

/** A fake Worker: the first one fails to download, the next ones load and answer. */
function fauxWorkers() {
  const crees = [];
  const creerWorker = () => {
    const rang = crees.length;
    const w = {
      onmessage: null,
      onerror: null,
      termine: false,
      terminate() { this.termine = true; },
      postMessage(m) {
        queueMicrotask(() => {
          if (m.type === 'charger') {
            if (rang === 0) w.onmessage({ data: { type: 'erreur', code: 'chargement', statut: 503 } });
            else w.onmessage({ data: { type: 'pret', resume: { index: {}, couverture: {} } } });
          } else if (m.type === 'chercher') {
            w.onmessage({ data: { type: 'correspondances', id: m.id, correspondances: [] } });
          }
        });
      },
    };
    crees.push(w);
    return w;
  };
  return { crees, creerWorker };
}

test('review: after a failed index download, the next search starts the download again (no cached rejection)', async () => {
  globalThis.document ??= { baseURI: 'http://127.0.0.1/' };
  const { crees, creerWorker } = fauxWorkers();
  const donnees = creerClientDonnees({ creerWorker });
  const phases = [];
  donnees.abonner((e) => phases.push(e.phase));
  await assert.rejects(donnees.chercher({ texte: 'Ali' }), (e) => e.name === 'ErreurDonnees' && e.code === 'chargement' && e.statut === 503);
  assert.equal(donnees.etat().phase, 'erreur');
  // the results-area « Réessayer » only runs the search again: it must reach a new worker
  const reponse = await donnees.chercher({ texte: 'Ali' });
  assert.equal(reponse.type, 'correspondances');
  assert.equal(crees.length, 2);
  assert.equal(crees[0].termine, true, 'the failed worker is dropped');
  assert.equal(donnees.etat().phase, 'pret');
  assert.ok(phases.indexOf('pret') > phases.indexOf('erreur'));
});

test('review: a failed search says the precise reason of the download, once', () => {
  assert.match(messageDEchec({ name: 'ErreurDonnees', code: 'chargement', statut: 503 }, T), /réponse 503/);
  assert.equal(messageDEchec({ name: 'ContenuIndisponible' }, T), T.erreurs.contenu);
  assert.equal(messageDEchec({ name: 'ErreurDonnees', code: 'abandon' }, T), T.erreurs.recherche);
  assert.notEqual(T.erreurs.titrePage, T.erreurs.titre, 'a guide page that fails is not « La recherche n\'a pas pu se faire »');
});

// ----- the reader's place, for "back" ----------------------------------------------------------

test('review: the position kept in a history entry is read defensively and merged, not replaced', () => {
  assert.equal(lirePosition(null), null);
  assert.equal(lirePosition({ autre: 1 }), null);
  const s = avecPosition({ autre: 1 }, { y: 5639, ouverts: ['an:12', 42, 'x'.repeat(400)], cible: { cle: 'an:12', href: '#/notice/an/FRAN_IR_000001/PERS001' } });
  assert.equal(s.autre, 1, 'other keys of history.state are kept');
  const p = lirePosition(s);
  assert.equal(p.y, 5639);
  assert.deepEqual(p.ouverts, ['an:12'], 'only short strings are kept');
  assert.equal(p.cible.cle, 'an:12');
  const s2 = avecPosition(s, { vue: { texte: 'Ali', fenetres: { correspondance: { debut: 0, fin: 20 } } } });
  assert.equal(lirePosition(s2).y, 5639, 'a later patch keeps the scroll');
  assert.equal(lirePosition(avecPosition(null, { y: -3 })).y, 0);
});

test('review: saved card windows are used only when they still fit the counts', () => {
  const totaux = { correspondance: 121, 'graphie-approchante': 3, partielle: 0 };
  const bonnes = { correspondance: { debut: 0, fin: 20 }, 'graphie-approchante': { debut: 0, fin: 3 }, partielle: { debut: 0, fin: 0 } };
  assert.deepEqual(fenetresSauvees(bonnes, totaux), bonnes);
  assert.equal(fenetresSauvees({ ...bonnes, correspondance: { debut: 0, fin: 500 } }, totaux), null);
  assert.equal(fenetresSauvees({ correspondance: { debut: 'a', fin: 2 } }, totaux), null);
  assert.equal(fenetresSauvees(null, totaux), null);
});

// ----- the year window and the birth-year tolerance --------------------------------------------

const couverture = creerModele(fichiers()).couverture();

test('review: « né vers 1878 » searched at five years either way keeps 1898 among the years to look at', () => {
  // without the tolerance the window started at 1899 and dropped 1898 (names at the Archives nationales)
  const c = conseilsPourAnnee(couverture, 1878, 21, 5);
  assert.equal(c.anneeMin, 1894);
  assert.ok(c.nomsAuxAn.includes(1898), JSON.stringify(c.nomsAuxAn));
  assert.equal(conseilsPourAnnee(couverture, 1878, 21).nomsAuxAn.includes(1898), false, 'no tolerance given: exact year');
  assert.deepEqual(fenetreAdmission(1878, { ageMinimal: 21, fin: 1948, tolerance: 5 }), { de: 1894, a: 1948 });
  assert.equal(fenetreAdmission(1878, { ageMinimal: 21, fin: 1948, tolerance: 'x' }).de, 1899, 'a junk tolerance counts as none');
});

test('review: the decree list follows the same tolerance when the bilan link carries it', () => {
  const dispo = [1890, 1894, 1899, 1905];
  assert.deepEqual(fenetreDemandee({ naissance: 1878, tolerance: 5 }, dispo, 21).annees, [1894, 1899, 1905]);
  assert.deepEqual(fenetreDemandee({ naissance: 1878 }, dispo, 21).annees, [1899, 1905]);
});

test('review: the two lists of « names held at the Archives nationales » come from one rule', () => {
  const ligne = (annee, lecture, algAvecNoms) => ({ annee, lecture, algAvecNoms, algDecrets: 3, inventaires: [] });
  const c = { an: { annees: [ligne(1898, 'noms-aux-an', 5), ligne(1900, 'image-en-partie', 1), ligne(1901, 'image-en-partie', 0), ligne(1904, 'image-en-partie', 0)], trimestres: [] }, bogga: { annees: [] } };
  const conseils = conseilsPourAnnee(c, 1870, 21, 5);
  const phrase = enoncerPeriodes(c.an.annees, c.an.trimestres, nomsAuxAnSeulement);
  assert.deepEqual(conseils.nomsAuxAn, [1898, 1900]);
  assert.equal(phrase, '1898 et 1900');
  // a year whose Algerian decrees hold no name is to be read on the images, and only there
  assert.ok(conseils.imagesSeules.includes(1901) && conseils.imagesSeules.includes(1904));
});

test('review: the bilan says that only the Algeria part of the Archives nationales index is read, with both counts', () => {
  const data = fichiers();
  data.anMeta.comptes.corpus = { notices_de_personnes: 371860 };
  const cv = creerModele(data).couverture();
  const index = buildIndex(occurrencesFromColumns(data.anPersonnes, { groupe: 'an' }).occurrences);
  const { bilan } = search(index, { texte: 'Introuvablaoui Mokhtar' });
  const b = composerBilan({ bilanMoteur: bilan, couverture: cv, contenu: lire('bilan'), etat: { texte: 'Introuvablaoui Mokhtar', annee: null }, ageMinimal: 21 });
  const ligne = plat(b.fouille.lignes.find((l) => l.id === 'an-index').texte);
  assert.match(ligne, /Seule la partie de l'index qui peut concerner l'Algérie est reprise/);
  assert.match(ligne, /3 notices de personnes sur 371 860/);
  assert.doesNotMatch(ligne, /\{[a-z_]+\}/);
});

test('review: « 70 correspondance(s) partielle(s) » is written with its real number', () => {
  const v = variablesDuBilan({ bilanMoteur: { comptes: { parClasse: { partielle: 70 } }, termes: [] }, couverture, etat: { texte: 'x' } });
  assert.equal(plat(v.partielles), '70 correspondances partielles');
  assert.equal(plat(variablesDuBilan({ bilanMoteur: { comptes: { parClasse: { partielle: 1 } }, termes: [] }, couverture, etat: { texte: 'x' } }).partielles), '1 correspondance partielle');
  assert.doesNotMatch(lire('bilan').resume.partielles_seulement, /\(s\)/);
});

// ----- same-date publications in the Bulletin ---------------------------------------------------

test('review: a publication of the same date is offered as THE publication only when the machine read the name in it', () => {
  const data = fichiers();
  // the entry of printed decree 1 names the household by its surname, as the 1885 lists do
  data.boggaEntrees.lignes[2][4] = 'Testaoui (Belkacem ben Exemplane), cultivateur, né en 1850, demeurant à Fictiville.';
  const fiche = creerModele(data).ficheAn(0);
  assert.equal(fiche.publications.length, 2, 'two printed decrees bear 10 March 1885');
  assert.equal(fiche.publications[0].ligne, 1, 'the recognised one first');
  assert.equal(fiche.publications[0].nomReconnu, true);
  assert.equal(fiche.publications[1].nomReconnu, false);
  // without the surname in the entries, none is recognised: no false « C'est la publication »
  assert.equal(creerModele(fichiers()).ficheAn(0).publications.some((p) => p.nomReconnu), false);
});

test('review: the words that find a household, and the sorts of decree that can publish an AN decree', () => {
  const mots = motsDuMenage([{ nom: 'Testaoui, Ali ben Exemple' }, { nom: 'Exemplaoui, Fatma' }, { nom: 'Ahmed' }]);
  assert.equal(mots.tous, false);
  assert.equal(menageReconnu(mots, new Set(['testaui'])), true);
  assert.equal(menageReconnu(mots, new Set(['ali', 'exemple'])), false, 'given names alone never recognise a household');
  const sansNom = motsDuMenage([{ nom: 'Ali ben Exemple' }]);
  assert.equal(sansNom.tous, true);
  assert.equal(menageReconnu(sansNom, new Set(['ali'])), false);
  assert.equal(menageReconnu(sansNom, new Set(['ali', 'exemple'])), true);
  assert.equal(natureCompatible('reintegration', 'admission'), false);
  assert.equal(natureCompatible('naturalisation', 'admission'), true);
  assert.equal(natureCompatible('divers', 'admission'), true, 'a family not compared');
});

// ----- the index: unreliable birth years are not filters -----------------------------------------

test('review: an impossible birth year (« suspecte ») or one paired by rank is kept as unknown by the index', () => {
  const data = fichiers();
  const iPrec = data.anPersonnes.champs.indexOf('prec');
  data.anPersonnes.tables.prec = ['', 'jour', 'conventionnelle', 'position', 'suspecte'];
  data.anPersonnes.lignes[5][iPrec] = 4; // Testaoui, Larbi: 1874 marked impossible
  const occ = sansAnneesDouteuses(occurrencesFromColumns(data.anPersonnes, { groupe: 'an' }).occurrences, data.anPersonnes);
  assert.equal(occ.find((o) => o.ligne === 5).anneeNaissance, null);
  assert.equal(occ.find((o) => o.ligne === 2).anneeNaissance, null, 'a child dated by its rank in a list');
  assert.equal(occ.find((o) => o.ligne === 0).anneeNaissance, 1850);
  const index = buildIndex(occ);
  const { correspondances } = search(index, { texte: 'Testaoui Larbi', annee: '1820' });
  assert.equal(correspondances.length, 1, 'kept, not set aside by the year');
});

// ----- the citation checker -------------------------------------------------------------------

test('review: « N° 262-1412 » is one bare number, not an article number followed by another number', () => {
  const r = classerSaisie('N° 262-1412');
  assert.deepEqual(r.formes.map((f) => [f.code, f.texte]), [['nombre-nu', '262-1412']]);
  assert.equal(r.bilan, 'numero-seul');
  assert.equal(classerSaisie('N° 262-1912').formes.some((f) => f.code === 'annee'), false);
  assert.equal(classerSaisie('N° 350, Bulletin officiel 1873').formes[0].code, 'article', 'a lone article number still reads as one');
});

test('review: « JO du 7 février 1927 page 1500 »: the date is that of the issue, not of the decree', () => {
  const r = classerSaisie('JO du 7 février 1927 page 1500');
  assert.deepEqual(r.dates, []);
  assert.deepEqual(r.datesPublication, ['1927-02-07']);
  assert.deepEqual(r.elements, { date: false, publication: true, pageOuDatePublication: true });
  assert.equal(r.bilan, 'publication-sans-date');
  const complet = classerSaisie('Décret du 12 mars 1903 — Bulletin officiel du 20 avril 1903, p. 412');
  assert.deepEqual(complet.dates, ['1903-03-12']);
  assert.equal(complet.bilan, 'complete');
});

test('review: the checker has its own sentence for a lone number (no « troisième étape » it does not show)', () => {
  assert.doesNotMatch(T.numero.numeroSeul.faire, /étape/);
  assert.ok(T.numero.publicationSansDate.faire.length > 20);
});

// ----- links ----------------------------------------------------------------------------------

test('review: an address copied in http from an inventory is given in https, like every link of the table', () => {
  const liens = creerLiens(tableDeLiens());
  const r = liens.particulier('http://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_000002/ZZ9/autre');
  assert.equal(r.url, 'https://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_000002/ZZ9/autre');
  assert.equal(liens.particulier('http://ailleurs.test/x'), null);
});

test('review: the pointer « Voir « observation » et « origine » » never reaches the page, even after the typography', () => {
  const table = typographierTout(tableDeLiens(), saufTechniques(new Set(['id', 'gabarit', 'hote', 'repli', 'statut', 'variables'])));
  const liens = creerLiens(table);
  const r = liens.resoudre('recherche-mot', { identifiant: 'x', mot: 'y' });
  assert.doesNotMatch(plat(r.note), /observation/);
  assert.match(plat(r.note), /^Personne n'a encore vu/);
});

// ----- typography -------------------------------------------------------------------------------

test('review: thousands never split across lines, and the sentences of whole guides are typographed', async () => {
  assert.equal(typographier('un peu plus de 6 000 Algériens'), 'un peu plus de 6 000 Algériens');
  assert.equal(typographier('de 1883 à 1897, 1913'), 'de 1883 à 1897, 1913', 'years are left alone');
  const contenu = creerContenu({ fetch: async () => ({ ok: true, json: async () => lire('guides') }) });
  const guides = await contenu.charger('guides');
  const instructions = guides.guides.flatMap((g) => g.etapes.map((e) => e.instruction));
  assert.ok(instructions.every((x) => !/ [:;?!](?=\s|$)/.test(x)), 'no ordinary space before a colon in a step');
  assert.equal(guides.guides[0].id, lire('guides').guides[0].id, 'identifiers are copied as they are');
  assert.deepEqual(guides.guides[0].etapes[0].liens, lire('guides').guides[0].etapes[0].liens);
});

// ----- what the user reads -----------------------------------------------------------------------

test('review: every statement of the content files that is not verified is shown with a note', () => {
  assert.equal(noteDeVerification({ etat: 'verifie', note: '' }), null);
  assert.equal(noteDeVerification(undefined), null);
  assert.equal(noteDeVerification({ etat: 'partiel', note: 'Vu pour 1873 seulement.' }), 'Vu pour 1873 seulement.');
  assert.equal(noteDeVerification({ etat: 'non-verifie', note: '' }), T.verification.nonVerifie);
  const arbre = lire('aiguillage');
  const bilan = lire('bilan');
  const blocs = [...arbre.issues, ...arbre.epoques, ...bilan.ce_qui_n_est_pas_couvert.lignes];
  const nonVerifies = blocs.filter((b) => b.verification.etat !== 'verifie');
  assert.ok(nonVerifies.length > 5);
  for (const b of nonVerifies) assert.ok(noteDeVerification(b.verification), b.id);
});

test('review: the hint rule is said in plain French, never as a machine code', () => {
  const texte = regleEnClair('ne-en-algerie(explicite)+prenom-musulman+filiation');
  assert.equal(plat(texte), 'naissance en Algérie écrite dans la notice ; prénom de forme arabe ou berbère ; nom du père introduit par « ben » ou « ould »');
  assert.doesNotMatch(regleEnClair('ne-patagonie+inconnue'), /[a-z]-[a-z]/);
});

test('review: plain French and honest promises of the interface', () => {
  assert.doesNotMatch(T.decrets.groupesAides.rejets, /explique une absence/);
  assert.doesNotMatch(T.accueil.engagements.map((e) => e.titre + e.texte).join(' '), /officielles|renvoie au document que chacun/);
  assert.match(T.accueil.promesse, /Bulletin officiel du Gouvernement général de l.Algérie/);
  assert.match(T.lus.rappel, /^N.avoir rien trouvé/);
  assert.match(T.fiche.avantImage, /adresse IP/);
  assert.doesNotMatch(T.aPropos.erreurTexte, /responsable du site/);
  assert.equal(plat(T.guide.duree('Une demi-heure.')), 'Durée : une demi-heure.');
  assert.doesNotMatch(T.formulaire.aideNom, /Chabane/);
});
