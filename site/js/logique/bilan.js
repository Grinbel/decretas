/**
 * The "bilan de recherche": what was searched, how, what was not and why. This module only
 * assembles facts — the engine's own report, the coverage tables generated with the data, the
 * texts of site/contenu/bilan.json — into a plain structure; composants/bilan.js draws it.
 * No year and no count is written here.
 */

import { T } from '../textes/index.js';
import { enoncerAnnees, enoncerTrimestres, enumerer, formaterDate, formaterNombre, libelleGraphie, plagesAnnees, remplirGabarit } from './formats.js';
import { conseilsPourAnnee, nomsAuxAnSeulement } from './fenetre-annees.js';
import { noteDeVerification } from './verification.js';

/**
 * Years (and, for the years cut into quarters, months) that pass a test, as a French phrase:
 * "1899 à 1912, avril à décembre 1928 et 1933 à 1948".
 * @param {Object[]} annees      coverage rows {annee, …}
 * @param {Object[]} trimestres  coverage rows {annee, trim, …} for the years cut into quarters
 * @param {(row: Object) => boolean} test
 */
export function enoncerPeriodes(annees, trimestres, test) {
  const quarters = new Map();
  for (const q of trimestres ?? []) {
    if (!quarters.has(q.annee)) quarters.set(q.annee, []);
    quarters.get(q.annee).push(q);
  }
  const items = []; // {annee, texte|null}  texte null: the whole year
  for (const y of [...(annees ?? [])].sort((a, b) => a.annee - b.annee)) {
    const qs = quarters.get(y.annee);
    if (qs === undefined) {
      if (test(y)) items.push({ annee: y.annee, texte: null });
      continue;
    }
    const kept = qs.filter(test).map((q) => q.trim);
    if (kept.length === 0) continue;
    if (kept.length === qs.length && qs.length === 4) items.push({ annee: y.annee, texte: null });
    else for (const text of enoncerTrimestres(kept)) items.push({ annee: y.annee, texte: T.formats.moisDeLAnnee(text, y.annee) });
  }
  const parts = [];
  let run = [];
  const flush = () => {
    for (const [de, a] of plagesAnnees(run)) {
      if (de === a) parts.push(String(de));
      else if (a === de + 1) parts.push(String(de), String(a));
      else parts.push(T.formats.plage(de, a));
    }
    run = [];
  };
  for (const item of items) {
    if (item.texte === null) run.push(item.annee);
    else {
      flush();
      parts.push(item.texte);
    }
  }
  flush();
  return enumerer(parts);
}

/** Values of the {variables} of bilan.json, from the data and from the search itself. */
export function variablesDuBilan({ bilanMoteur, couverture, etat }) {
  const an = couverture?.an ?? { annees: [], trimestres: [] };
  const bogga = couverture?.bogga ?? { annees: [] };
  const comptes = bilanMoteur?.comptes?.parClasse ?? {};
  const termes = (bilanMoteur?.termes ?? []).map((t) => t.saisie);
  const variantes = (bilanMoteur?.termes ?? []).reduce((sum, t) => sum + t.variantes.length, 0);
  const naissance = Number.isInteger(etat?.annee) ? etat.annee : null;
  return {
    termes: termes.length > 0 ? termes.map((x) => T.formats.cite(x)).join(T.formats.virgule) : T.formats.cite(String(etat?.texte ?? '')),
    nb_variantes: variantes,
    annees_an: enoncerPeriodes(an.annees, an.trimestres, (y) => y.lecture === 'lue' || y.lecture === 'lue-en-partie'),
    date_donnees_an: formaterDate(an.releveLe),
    annees_bulletin: enoncerAnnees(bogga.annees.filter((y) => y.lu).map((y) => y.annee)),
    annees_images_seules: enoncerPeriodes(an.annees, an.trimestres, (y) => y.lecture === 'image' || y.lecture === 'image-en-partie' || y.lecture === 'lue-en-partie'),
    annees_noms_non_repris: enoncerPeriodes(an.annees, an.trimestres, nomsAuxAnSeulement),
    nb_correspondances: (comptes.correspondance ?? 0) + (comptes['graphie-approchante'] ?? 0),
    nb_partielles: comptes.partielle ?? 0,
    partielles: T.bilan.partielles(comptes.partielle ?? 0),
    an_notices_reprises: Number.isFinite(an.principaux) ? formaterNombre(an.principaux) : '?',
    an_notices_index: Number.isFinite(an.noticesIndex) ? formaterNombre(an.noticesIndex) : '?',
    annee_naissance: naissance,
    tolerance_naissance: Number.isInteger(bilanMoteur?.annee?.tolerance) ? bilanMoteur.annee.tolerance : 0,
    annee_min: null, // set by the caller, which knows the legal minimum age
  };
}

/** Which summary sentence of bilan.json applies. */
export function cleDuResume(comptes) {
  const full = (comptes?.correspondance ?? 0) + (comptes?.['graphie-approchante'] ?? 0);
  if (full === 1) return 'une_correspondance';
  if (full > 1) return 'plusieurs_correspondances';
  if ((comptes?.partielle ?? 0) > 0) return 'partielles_seulement';
  return 'aucune';
}

/**
 * @param {Object} entree
 * @param {Object} entree.bilanMoteur  "bilan" of the engine for this search
 * @param {Object} entree.couverture   coverage summary of the data layer
 * @param {Object} entree.contenu      parsed site/contenu/bilan.json
 * @param {Object} entree.etat         state of the search {texte, annee, tolerance, exclusions, ajouts}
 * @param {number} entree.ageMinimal   legal minimum age for a decree (aiguillage.json)
 * @returns {Object} the bilan, ready to draw (see composants/bilan.js)
 */
export function composerBilan({ bilanMoteur, couverture, contenu, etat, ageMinimal }) {
  const B = T.bilan;
  const variables = variablesDuBilan({ bilanMoteur, couverture, etat });
  const naissance = variables.annee_naissance;
  // The engine keeps the notices born within the tolerance: the window starts from the earliest.
  const tolerance = variables.tolerance_naissance;
  if (naissance !== null) variables.annee_min = naissance - tolerance + ageMinimal;
  const comptes = bilanMoteur.comptes;
  const index = bilanMoteur.index ?? {};
  const an = couverture.an;
  const bogga = couverture.bogga;

  // --- what was searched ---------------------------------------------------------------
  const fouille = [];
  for (const ligne of contenu.ce_qui_a_ete_fouille?.lignes ?? []) {
    if (ligne.id === 'maniere') continue; // replaced below by the rules the engine really applied
    if (ligne.id === 'fenetre-naissance' && naissance === null) continue;
    const item = { id: ligne.id, texte: remplirGabarit(ligne.gabarit, variables), precisions: [] };
    if (ligne.id === 'an-index' && Number.isFinite(index.parGroupe?.an)) {
      item.precisions.push(B.nomsAn(index.parGroupe.an, an.epouses ?? 0, an.enfants ?? 0));
    }
    if (ligne.id === 'bulletin' && Number.isFinite(index.parGroupe?.bogga)) {
      item.precisions.push(B.nomsBulletin(index.parGroupe.bogga, bogga.decrets ?? 0));
    }
    fouille.push(item);
  }

  // --- how: the rules really applied, from the engine's report ----------------------------
  const regles = [];
  const termes = bilanMoteur.termes ?? [];
  if (termes.length > 0) {
    regles.push(B.termesCompris(termes.map((t) => {
      const others = t.variantes.slice(1).map((v) => v.saisie);
      return others.length > 0 ? B.termeAvecVariantes(t.saisie, others) : T.formats.cite(t.saisie);
    })));
  }
  const exclues = termes.flatMap((t) => t.graphiesExclues ?? []);
  if (exclues.length > 0) regles.push(B.graphiesExclues(exclues));
  const particules = [...new Set((bilanMoteur.particulesIgnorees ?? []).map((p) => p.saisie))];
  if (particules.length > 0) regles.push(B.particules(particules));
  const niveaux = bilanMoteur.regles?.niveaux ?? [];
  if (niveaux.includes('k0')) regles.push(B.regleK0);
  if (niveaux.includes('k1')) regles.push(B.regleK1);
  if (niveaux.includes('k2')) regles.push(B.regleK2(bilanMoteur.regles?.k2?.lettresMin));
  regles.push(bilanMoteur.regles?.partielles ? B.reglePartielles : B.reglePasDePartielles);
  if (termes.some((t) => t.variantes.some((v) => v.ecriture === 'arabe'))) regles.push(B.regleArabe);
  if (bilanMoteur.annee) {
    const y = bilanMoteur.annee;
    regles.push(B.regleAnnee(y.valeur, y.tolerance, y.de, y.a));
    const e = comptes.ecarteesParAnnee ?? {};
    const ecartees = (e.correspondance ?? 0) + (e['graphie-approchante'] ?? 0) + (e.partielle ?? 0);
    regles.push(B.ecarteesParAnnee(ecartees, comptes.sansAnneeDeNaissance ?? 0));
  } else {
    regles.push(B.regleSansAnnee);
  }
  regles.push(B.regleOrdre);

  const graphies = (bilanMoteur.graphiesTrouvees ?? []).map((g) => ({
    terme: g.terme,
    tronque: g.tronque === true,
    graphies: g.graphies.map((x) => ({
      graphie: libelleGraphie(x),
      occurrences: x.occurrences,
      approchante: x.niveau === 'k2' || x.arabe === true || x.soudure === 'prefixe-source' || x.soudure === 'prefixe-saisie',
    })),
  }));

  const parSource = Object.entries(comptes.parGroupe ?? {}).map(([groupe, c]) => ({
    groupe,
    libelle: T.sources[groupe]?.court ?? groupe,
    correspondance: c.correspondance ?? 0,
    approchante: c['graphie-approchante'] ?? 0,
    partielle: c.partielle ?? 0,
  }));

  // --- what was not searched, and why ---------------------------------------------------
  const nonCouvert = (contenu.ce_qui_n_est_pas_couvert?.lignes ?? []).map((ligne) => ({
    id: ligne.id,
    titre: remplirGabarit(ligne.titre, variables),
    texte: remplirGabarit(ligne.texte, variables),
    pourquoi: remplirGabarit(ligne.pourquoi, variables),
    queFaire: remplirGabarit(ligne.que_faire, variables),
    // a line that is not verified says so (« À confirmer : … »)
    aConfirmer: noteDeVerification(ligne.verification),
    verification: ligne.verification ?? null,
    guides: ligne.guides ?? [],
  }));
  const volumesSansDecret = bogga.annees.filter((y) => y.lu && y.decrets === 0 && y.queFaire).map((y) => ({ annee: y.annee, texte: y.queFaire }));
  const anneesAbsentes = bogga.annees.filter((y) => !y.lu && y.queFaire).map((y) => ({ annee: y.annee, texte: y.queFaire }));

  return {
    variables,
    cleResume: cleDuResume(comptes.parClasse),
    resume: remplirGabarit(contenu.resume?.[cleDuResume(comptes.parClasse)], variables),
    principe: contenu.principe ?? '',
    fouille: { titre: contenu.ce_qui_a_ete_fouille?.titre ?? '', lignes: fouille, note: contenu.ce_qui_a_ete_fouille?.note ?? '' },
    regles,
    graphies,
    parSource,
    nonCouvert: {
      titre: contenu.ce_qui_n_est_pas_couvert?.titre ?? '',
      lignes: nonCouvert,
      pagesALireALaMain: bogga.pagesALireALaMain ?? [],
      volumesSansDecret,
      anneesAbsentes,
      avertissementsBulletin: bogga.avertissements ?? [],
    },
    rappelJugement: contenu.rappel_jugement ?? null,
    conseils: conseilsPourAnnee(couverture, naissance, ageMinimal, tolerance),
    ageMinimal,
    demarches: contenu.demarches_restantes ?? { titre: '', lignes: [] },
    misesEnGarde: contenu.mises_en_garde ?? null,
    pied: contenu.ce_que_ce_bilan_n_est_pas ?? '',
    tronque: bilanMoteur.tronque ?? {},
    limiteParClasse: bilanMoteur.limiteParClasse ?? null,
  };
}
